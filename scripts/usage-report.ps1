<#
.SYNOPSIS
  Reports what a project's Claude Code sessions spent, per session and per kind of sub-agent,
  read from the local transcripts (~/.claude/projects/<project>/**/*.jsonl).

.DESCRIPTION
  Use it to compare the workflow plugin before and after a change: review gates per epic,
  spike calls, the largest context each session reached, and where the input tokens went.

  Limits: the numbers are input-side (cache reads, cache writes, uncached input). Transcripts
  under-report output tokens, sub-agents' most of all, so OutK is a floor, not a total.
  A fix round sent with SendMessage continues an agent's transcript instead of starting a new
  one: count those in the main session's Tools column.

.EXAMPLE
  pwsh scripts/usage-report.ps1 -Project limaj-framework -Days 7
  pwsh scripts/usage-report.ps1 -Project limaj-framework -Session 6e02ab93 -Detail
#>
param(
    [Parameter(Mandatory)][string]$Project,        # part of the folder name under ~/.claude/projects
    [int]$Days = 7,
    [string]$Session,                              # session id prefix; with -Detail, the transcript to open
    [switch]$Detail,                               # per-tool sizes and the context timeline of one main session
    [string]$ProjectsRoot = (Join-Path $HOME '.claude/projects')
)

function Read-Transcript([string]$Path) {
    foreach ($line in [System.IO.File]::ReadLines($Path)) {
        if (-not $line) { continue }
        try { $line | ConvertFrom-Json -Depth 50 } catch { }
    }
}

function Get-Stats([string]$Path) {
    $seen = @{}; $tools = @{}
    $read = 0L; $write = 0L; $in = 0L; $out = 0L; $maxCtx = 0L; $reqs = 0
    $model = ''; $first = $null; $last = $null; $prompt = ''
    foreach ($o in Read-Transcript $Path) {
        if ($o.timestamp) { if (-not $first) { $first = $o.timestamp }; $last = $o.timestamp }
        if ($o.type -eq 'user' -and -not $prompt) {
            $c = $o.message.content
            $prompt = if ($c -is [string]) { $c } else { ($c | Where-Object type -eq 'text' | ForEach-Object text) -join ' ' }
        }
        if ($o.type -ne 'assistant') { continue }
        foreach ($b in $o.message.content) { if ($b.type -eq 'tool_use') { $tools[$b.name] = 1 + [int]$tools[$b.name] } }
        $id = $o.message.id; $u = $o.message.usage
        if (-not $id -or $seen.ContainsKey($id) -or -not $u) { continue }
        $seen[$id] = 1; $reqs++
        $read += [long]$u.cache_read_input_tokens; $write += [long]$u.cache_creation_input_tokens
        $in += [long]$u.input_tokens; $out += [long]$u.output_tokens
        $ctx = [long]$u.input_tokens + [long]$u.cache_read_input_tokens + [long]$u.cache_creation_input_tokens
        if ($ctx -gt $maxCtx) { $maxCtx = $ctx }
        if ($o.message.model -and $o.message.model -ne '<synthetic>') { $model = $o.message.model -replace '^claude-', '' }
    }
    $minutes = if ($first -and $last) { [math]::Round((([datetime]$last) - ([datetime]$first)).TotalMinutes, 1) } else { 0 }
    [pscustomobject]@{
        Reqs = $reqs; MaxCtxK = [math]::Round($maxCtx / 1000); CacheReadK = [math]::Round($read / 1000)
        CacheWriteK = [math]::Round($write / 1000); InK = [math]::Round($in / 1000); OutK = [math]::Round($out / 1000)
        Min = $minutes; Model = $model; Start = $first; Prompt = $prompt
        Tools = ($tools.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ' '
    }
}

function Get-Kind([string]$Prompt, [string]$AgentType) {
    $fix = if ($Prompt -match '\[FIX REQUEST\]\s*Kind:\s*([\w-]+)') { $Matches[1] } else { '' }
    if ($AgentType -match '(^|:)spike$' -or $Prompt -match 'Epic implementation under /flow') {
        if ($fix) { return "spike-fix-$fix" }
        if ($Prompt -match '\[HANDOFF\]\s*HANDOFF') { return 'spike-handoff' }
        return 'spike-slice'
    }
    if ($Prompt -match 'Open findings:') { return 'review-delta' }
    if ($Prompt -match 'register of every rule') { return 'review-standards' }
    if ($Prompt -match 'spec asks for that are missing|Spec reviewer') { return 'review-spec' }
    if ($Prompt -match 'Minimize the interface|Maximize flexibility|most common caller|existing pattern and its UI') { return 'design' }
    if ($AgentType -and $AgentType -ne 'general-purpose') { return $AgentType }
    return 'other'
}

$dir = Get-ChildItem $ProjectsRoot -Directory | Where-Object Name -like "*$Project*" | Select-Object -First 1
if (-not $dir) { throw "No project folder matching '$Project' under $ProjectsRoot" }
$since = (Get-Date).AddDays(-$Days)
$files = Get-ChildItem $dir.FullName -Recurse -Filter *.jsonl -File | Where-Object LastWriteTime -gt $since
if ($Session) { $files = $files | Where-Object FullName -like "*$Session*" }
if (-not $files) { throw "No transcripts in the last $Days days for $($dir.Name)" }

if ($Detail) {
    $main = $files | Where-Object { $_.FullName -notmatch 'subagents' } | Sort-Object Length -Descending | Select-Object -First 1
    "Detail of $($main.Name)"
    $byTool = @{}; $pending = @{}; $seen = @{}
    foreach ($o in Read-Transcript $main.FullName) {
        if ($o.type -eq 'assistant') {
            $u = $o.message.usage; $id = $o.message.id
            if ($id -and $u -and -not $seen.ContainsKey($id)) {
                $seen[$id] = 1
                $ctx = [long]$u.input_tokens + [long]$u.cache_read_input_tokens + [long]$u.cache_creation_input_tokens
                "{0}  ctx {1,5}k  cache-write {2,4}k" -f ([datetime]$o.timestamp).ToString('HH:mm:ss'), [math]::Round($ctx / 1000), [math]::Round([long]$u.cache_creation_input_tokens / 1000)
            }
            foreach ($b in $o.message.content) {
                if ($b.type -ne 'tool_use') { continue }
                $size = ($b.input | ConvertTo-Json -Depth 20 -Compress).Length
                $pending[$b.id] = $b.name
                if (-not $byTool.ContainsKey($b.name)) { $byTool[$b.name] = [pscustomobject]@{ Tool = $b.name; Calls = 0; InputChars = 0; ResultChars = 0 } }
                $byTool[$b.name].Calls++; $byTool[$b.name].InputChars += $size
                if ($b.name -in 'Agent', 'Task', 'SendMessage') { "{0}  -> {1} {2} {3}" -f ([datetime]$o.timestamp).ToString('HH:mm:ss'), $b.name, $b.input.subagent_type, "$($b.input.description)$($b.input.to)" }
            }
        }
        elseif ($o.type -eq 'user' -and $o.message.content -isnot [string]) {
            foreach ($b in $o.message.content) {
                if ($b.type -ne 'tool_result' -or -not $pending.ContainsKey($b.tool_use_id)) { continue }
                $text = if ($b.content -is [string]) { $b.content } else { ($b.content | ForEach-Object text) -join '' }
                $byTool[$pending[$b.tool_use_id]].ResultChars += $text.Length
            }
        }
    }
    "`nBy tool (tokens ~ chars / 4):"
    $byTool.Values | Select-Object Tool, Calls, @{N = 'InputK'; E = { [math]::Round($_.InputChars / 4000, 1) } }, @{N = 'ResultK'; E = { [math]::Round($_.ResultChars / 4000, 1) } } |
        Sort-Object ResultK -Descending | Format-Table -AutoSize
    return
}

$rows = foreach ($f in $files) {
    $s = Get-Stats $f.FullName
    $isSub = $f.FullName -match 'subagents'
    $agentType = ''
    if ($isSub) {
        $meta = $f.FullName -replace '\.jsonl$', '.meta.json'
        if (Test-Path $meta) { try { $agentType = (Get-Content $meta -Raw | ConvertFrom-Json).agentType } catch { } }
    }
    [pscustomobject]@{
        Session = if ($isSub) { $f.Directory.Parent.Name.Substring(0, 8) } else { $f.BaseName.Substring(0, 8) }
        Kind = if ($isSub) { Get-Kind $s.Prompt $agentType } else { 'MAIN' }
        Start = if ($s.Start) { ([datetime]$s.Start).ToString('MM-dd HH:mm') } else { '' }
        Min = $s.Min; Reqs = $s.Reqs; MaxCtxK = $s.MaxCtxK; CacheReadK = $s.CacheReadK; CacheWriteK = $s.CacheWriteK
        InK = $s.InK; OutK = $s.OutK; Model = $s.Model; Tools = $s.Tools
    }
}
$rows = $rows | Sort-Object Session, Start

"Transcripts — $($dir.Name), last $Days days"
$rows | Format-Table Session, Kind, Start, Min, Reqs, MaxCtxK, CacheReadK, CacheWriteK, OutK, Model -AutoSize

"Totals by kind"
$rows | Group-Object Kind | ForEach-Object {
    [pscustomobject]@{
        Kind = $_.Name; Calls = $_.Count
        MaxCtxK = ($_.Group | Measure-Object MaxCtxK -Maximum).Maximum
        CacheReadK = ($_.Group | Measure-Object CacheReadK -Sum).Sum
        CacheWriteK = ($_.Group | Measure-Object CacheWriteK -Sum).Sum
        OutK = ($_.Group | Measure-Object OutK -Sum).Sum
    }
} | Sort-Object CacheReadK -Descending | Format-Table -AutoSize

"Per session — the numbers to compare between plugin versions"
$rows | Group-Object Session | ForEach-Object {
    $g = $_.Group; $main = $g | Where-Object Kind -eq 'MAIN' | Select-Object -First 1
    [pscustomobject]@{
        Session = $_.Name
        SubAgents = @($g | Where-Object Kind -ne 'MAIN').Count
        SpikeCalls = @($g | Where-Object Kind -like 'spike-*').Count
        FullReviews = @($g | Where-Object Kind -eq 'review-standards').Count
        DeltaReviews = @($g | Where-Object Kind -eq 'review-delta').Count
        MainMaxCtxK = $main.MaxCtxK
        SpikeMaxCtxK = ($g | Where-Object Kind -like 'spike-*' | Measure-Object MaxCtxK -Maximum).Maximum
        CacheReadK = ($g | Measure-Object CacheReadK -Sum).Sum
        CacheWriteK = ($g | Measure-Object CacheWriteK -Sum).Sum
        MainTools = $main.Tools
    }
} | Format-Table -AutoSize -Wrap
