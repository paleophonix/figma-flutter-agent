# Send synthetic GitLab webhook payloads to a local control plane for smoke testing.
param(
    [ValidateSet("issue-open", "issue-close", "note-bug", "note-fix")]
    [string]$Event = "issue-open",
    [string]$BaseUrl = "http://127.0.0.1:8787",
    [string]$WebhookSecret = "",
    [string]$ProjectId = "12345",
    [int]$IssueIid = 1,
    [string]$FigmaUrl = "https://www.figma.com/design/test/App?node-id=1-2",
    [string]$AgentUsername = "figma-bot",
    [string]$IssueUrl = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-WebhookSecret {
    param([string]$Explicit)
    if ($Explicit.Trim()) {
        return $Explicit.Trim()
    }
    $fromEnv = [string]$env:DISCORD_BOT_GITLAB_WEBHOOK_SECRET
    if ($fromEnv.Trim()) {
        return $fromEnv.Trim()
    }
    throw "Webhook secret missing. Set DISCORD_BOT_GITLAB_WEBHOOK_SECRET in .env or pass -WebhookSecret."
}

function Build-Payload {
    param(
        [string]$Kind,
        [string]$Project,
        [int]$Iid,
        [string]$Figma,
        [string]$Agent,
        [string]$Url
    )
    $issueUrl = if ($Url.Trim()) { $Url.Trim() } else { "https://gitlab.com/example/project/-/issues/$Iid" }

    switch ($Kind) {
        "issue-open" {
            return @{
                object_kind = "issue"
                project     = @{ id = $Project }
                assignees   = @(@{ username = $Agent })
                object_attributes = @{
                    action      = "open"
                    state       = "opened"
                    iid         = $Iid
                    url         = $issueUrl
                    description = "Frame: $Figma"
                }
            }
        }
        "issue-close" {
            return @{
                object_kind = "issue"
                project     = @{ id = $Project }
                object_attributes = @{
                    action = "close"
                    state  = "closed"
                    iid    = $Iid
                    url    = $issueUrl
                }
            }
        }
        "note-bug" {
            return @{
                object_kind = "note"
                project     = @{ id = $Project }
                issue       = @{ iid = $Iid }
                object_attributes = @{
                    noteable_type = "Issue"
                    note          = "/bug layout overflow on login button"
                }
            }
        }
        "note-fix" {
            return @{
                object_kind = "note"
                project     = @{ id = $Project }
                issue       = @{ iid = $Iid }
                object_attributes = @{
                    noteable_type = "Issue"
                    note          = "/fix"
                }
            }
        }
        default { throw "Unknown event: $Kind" }
    }
}

$secret = Resolve-WebhookSecret -Explicit $WebhookSecret
$payload = Build-Payload -Kind $Event -Project $ProjectId -Iid $IssueIid -Figma $FigmaUrl -Agent $AgentUsername -Url $IssueUrl
$body = $payload | ConvertTo-Json -Depth 8 -Compress
$uri = "$($BaseUrl.TrimEnd('/'))/webhooks/gitlab"

Write-Host "POST $uri"
Write-Host "Event: $Event  project=$ProjectId  issue_iid=$IssueIid"

$response = Invoke-RestMethod -Method Post -Uri $uri -Headers @{
    "X-Gitlab-Token" = $secret
    "Content-Type"   = "application/json"
} -Body $body

Write-Host "Response: $($response | ConvertTo-Json -Compress)"
Write-Host ""
Write-Host "Next: watch worker logs, Postgres jobs table, and GitLab issue comments (if token + project are real)."
