# Phase 4: Backend API Updates

**Timeline:** Week 2, Day 5 - Week 3, Day 1
**Goal:** Support span upserts for progressive states

## Overview

Updates backend API to handle duplicate span IDs with different states (running → completed). Implements upsert logic and SignalR events for real-time UI updates.

## Prerequisites

- ✅ Phase 3 completed
- ✅ CLI integration working
- ✅ Simplified spans being exported

## Tasks

### 1. Implement Span Upsert Logic

**Modify:** `src/UiPath.LLMOps.Observability/Controllers/TracesController.cs`

**Current implementation** (approximate):
```csharp
[HttpPost("spans")]
public async Task<IActionResult> CreateSpans(
    [FromBody] List<SpanDto> spans,
    CancellationToken cancellationToken)
{
    foreach (var span in spans)
    {
        await _spanRepository.InsertAsync(span, cancellationToken);
    }

    return Ok();
}
```

**Updated implementation** (with upsert):
```csharp
[HttpPost("spans")]
public async Task<IActionResult> UpsertSpans(
    [FromBody] List<SpanDto> spans,
    CancellationToken cancellationToken)
{
    var upsertedSpans = new List<SpanDto>();

    foreach (var span in spans)
    {
        // Check if span already exists
        var existing = await _spanRepository.GetByIdAsync(
            span.Id,
            cancellationToken
        );

        if (existing != null)
        {
            // Handle duplicate span ID
            // Rule: Don't overwrite completed span with running span
            if (existing.Status == 1 && span.Status == 0)
            {
                // Ignore stale "running" update
                _logger.LogDebug(
                    "Ignoring stale running update for completed span {SpanId}",
                    span.Id
                );
                continue;
            }

            // Otherwise, update (last write wins)
            await _spanRepository.UpdateAsync(span, cancellationToken);
            upsertedSpans.Add(span);

            _logger.LogInformation(
                "Updated span {SpanId}: Status {OldStatus} -> {NewStatus}",
                span.Id,
                existing.Status,
                span.Status
            );
        }
        else
        {
            // New span, insert
            await _spanRepository.InsertAsync(span, cancellationToken);
            upsertedSpans.Add(span);

            _logger.LogInformation(
                "Inserted new span {SpanId} with status {Status}",
                span.Id,
                span.Status
            );
        }

        // Emit SignalR event for UI update
        await _traceHub.Clients.Group(span.TraceId.ToString())
            .SendAsync("SpanUpdated", span, cancellationToken);
    }

    return Ok(new { upserted = upsertedSpans.Count });
}
```

**Key logic:**
- Check if span exists by ID
- If exists and completed, ignore running updates
- Otherwise, last write wins
- Emit SignalR event on every upsert

### 2. Add SignalR Events

**Modify:** `src/UiPath.LLMOps.Observability/Hubs/TraceHub.cs`

**Current implementation:**
```csharp
public class TraceHub : Hub
{
    public async Task SubscribeToTrace(Guid traceId)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, traceId.ToString());
    }

    public async Task UnsubscribeFromTrace(Guid traceId)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, traceId.ToString());
    }
}
```

**No changes needed** - hub already supports groups and SendAsync.

**Events emitted:**
- `SpanUpdated`: When span state changes (running → completed)

**Event payload:**
```json
{
  "id": "synthetic-abc-001",
  "traceId": "trace-abc",
  "name": "Agent run - Agent",
  "status": 1,
  "startTime": "2025-01-19T10:00:00Z",
  "endTime": "2025-01-19T10:00:45Z",
  "attributes": {...}
}
```

### 3. Update Repository Interface

**Modify:** `src/UiPath.LLMOps.Observability/Repositories/ISpanRepository.cs`

**Add methods:**
```csharp
public interface ISpanRepository
{
    // Existing methods
    Task<SpanDto> InsertAsync(SpanDto span, CancellationToken ct);
    Task<List<SpanDto>> GetByTraceIdAsync(Guid traceId, CancellationToken ct);

    // New methods for upsert support
    Task<SpanDto?> GetByIdAsync(Guid spanId, CancellationToken ct);
    Task<SpanDto> UpdateAsync(SpanDto span, CancellationToken ct);
}
```

**Implement in:** `SpanRepository.cs`

```csharp
public async Task<SpanDto?> GetByIdAsync(Guid spanId, CancellationToken ct)
{
    var query = "SELECT * FROM Spans WHERE Id = @SpanId";

    using var connection = await _dbFactory.CreateConnectionAsync(ct);
    return await connection.QuerySingleOrDefaultAsync<SpanDto>(
        query,
        new { SpanId = spanId }
    );
}

public async Task<SpanDto> UpdateAsync(SpanDto span, CancellationToken ct)
{
    var query = @"
        UPDATE Spans
        SET
            Name = @Name,
            Status = @Status,
            StartTime = @StartTime,
            EndTime = @EndTime,
            Attributes = @Attributes,
            UpdatedAt = @UpdatedAt
        WHERE Id = @Id
    ";

    span.UpdatedAt = DateTime.UtcNow;

    using var connection = await _dbFactory.CreateConnectionAsync(ct);
    await connection.ExecuteAsync(query, span);

    return span;
}
```

### 4. Add Database Migration

**Create:** `migrations/add_updated_at_column.sql`

```sql
-- Add UpdatedAt column to track when span was last modified
ALTER TABLE Spans
ADD COLUMN UpdatedAt DATETIME2 NULL;

-- Set default for existing rows
UPDATE Spans
SET UpdatedAt = CreatedAt
WHERE UpdatedAt IS NULL;

-- Make column NOT NULL after backfill
ALTER TABLE Spans
ALTER COLUMN UpdatedAt DATETIME2 NOT NULL;

-- Add index for efficient lookups
CREATE INDEX IX_Spans_UpdatedAt ON Spans(UpdatedAt);
```

**Apply:**
```bash
dotnet ef migrations add AddUpdatedAtColumn
dotnet ef database update
```

### 5. Testing

**Create:** `tests/Controllers/TracesControllerTests.cs`

```csharp
public class TracesControllerUpsertTests
{
    private readonly Mock<ISpanRepository> _mockRepo;
    private readonly Mock<IHubContext<TraceHub>> _mockHub;
    private readonly TracesController _controller;

    public TracesControllerUpsertTests()
    {
        _mockRepo = new Mock<ISpanRepository>();
        _mockHub = new Mock<IHubContext<TraceHub>>();
        _controller = new TracesController(_mockRepo.Object, _mockHub.Object);
    }

    [Fact]
    public async Task UpsertSpans_NewSpan_InsertsSuccessfully()
    {
        // Arrange
        var span = new SpanDto
        {
            Id = Guid.NewGuid(),
            TraceId = Guid.NewGuid(),
            Name = "Agent run - Agent",
            Status = 0
        };

        _mockRepo.Setup(r => r.GetByIdAsync(span.Id, It.IsAny<CancellationToken>()))
            .ReturnsAsync((SpanDto?)null);

        // Act
        var result = await _controller.UpsertSpans(
            new List<SpanDto> { span },
            CancellationToken.None
        );

        // Assert
        _mockRepo.Verify(r => r.InsertAsync(span, It.IsAny<CancellationToken>()), Times.Once);
        _mockRepo.Verify(r => r.UpdateAsync(It.IsAny<SpanDto>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task UpsertSpans_ExistingRunningSpan_UpdatesToCompleted()
    {
        // Arrange
        var spanId = Guid.NewGuid();
        var existingSpan = new SpanDto
        {
            Id = spanId,
            Status = 0,  // Running
            EndTime = null
        };

        var updatedSpan = new SpanDto
        {
            Id = spanId,
            Status = 1,  // Completed
            EndTime = DateTime.UtcNow
        };

        _mockRepo.Setup(r => r.GetByIdAsync(spanId, It.IsAny<CancellationToken>()))
            .ReturnsAsync(existingSpan);

        // Act
        await _controller.UpsertSpans(
            new List<SpanDto> { updatedSpan },
            CancellationToken.None
        );

        // Assert
        _mockRepo.Verify(r => r.UpdateAsync(updatedSpan, It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task UpsertSpans_CompletedSpan_IgnoresRunningUpdate()
    {
        // Arrange
        var spanId = Guid.NewGuid();
        var completedSpan = new SpanDto
        {
            Id = spanId,
            Status = 1,  // Completed
            EndTime = DateTime.UtcNow
        };

        var staleUpdate = new SpanDto
        {
            Id = spanId,
            Status = 0,  // Running (stale)
            EndTime = null
        };

        _mockRepo.Setup(r => r.GetByIdAsync(spanId, It.IsAny<CancellationToken>()))
            .ReturnsAsync(completedSpan);

        // Act
        await _controller.UpsertSpans(
            new List<SpanDto> { staleUpdate },
            CancellationToken.None
        );

        // Assert
        _mockRepo.Verify(r => r.UpdateAsync(It.IsAny<SpanDto>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task UpsertSpans_EmitsSignalREvent()
    {
        // Arrange
        var span = new SpanDto
        {
            Id = Guid.NewGuid(),
            TraceId = Guid.NewGuid(),
            Name = "Agent run - Agent",
            Status = 1
        };

        _mockRepo.Setup(r => r.GetByIdAsync(span.Id, It.IsAny<CancellationToken>()))
            .ReturnsAsync((SpanDto?)null);

        var mockClients = new Mock<IHubClients>();
        var mockGroup = new Mock<IClientProxy>();

        _mockHub.Setup(h => h.Clients).Returns(mockClients.Object);
        mockClients.Setup(c => c.Group(span.TraceId.ToString())).Returns(mockGroup.Object);

        // Act
        await _controller.UpsertSpans(
            new List<SpanDto> { span },
            CancellationToken.None
        );

        // Assert
        mockGroup.Verify(
            g => g.SendCoreAsync(
                "SpanUpdated",
                It.Is<object[]>(o => o[0] == span),
                It.IsAny<CancellationToken>()
            ),
            Times.Once
        );
    }
}
```

**Run:**
```bash
dotnet test --filter FullyQualifiedName~TracesControllerUpsertTests
```

## Success Criteria

- ✅ API accepts duplicate span IDs
- ✅ Last update wins (completed > running)
- ✅ Stale updates ignored
- ✅ SignalR events emitted correctly
- ✅ Database migration applied
- ✅ All tests pass
- ✅ No regressions in existing functionality

## Deliverables

1. Updated `TracesController.cs` with upsert logic
2. Updated `ISpanRepository.cs` and `SpanRepository.cs`
3. Database migration for `UpdatedAt` column
4. `TracesControllerUpsertTests.cs` test suite
5. API documentation updates

## Timeline

- **Day 5 AM:** Implement upsert logic in controller
- **Day 5 PM:** Update repository and add migration
- **Week 3, Day 1 AM:** Write unit tests
- **Week 3, Day 1 PM:** Integration testing, deploy to dev

## API Contract

**Request:**
```json
POST /api/traces/spans

[
  {
    "id": "synthetic-abc-001",
    "traceId": "trace-abc",
    "name": "Agent run - Agent",
    "status": 0,
    "startTime": "2025-01-19T10:00:00Z",
    "endTime": null
  }
]
```

**Response:**
```json
{
  "upserted": 1
}
```

**SignalR Event:**
```javascript
// Client receives on "SpanUpdated" event
{
  "id": "synthetic-abc-001",
  "traceId": "trace-abc",
  "name": "Agent run - Agent",
  "status": 1,
  "startTime": "2025-01-19T10:00:00Z",
  "endTime": "2025-01-19T10:00:45Z"
}
```

## Database Schema Changes

**Before:**
```sql
CREATE TABLE Spans (
    Id UNIQUEIDENTIFIER PRIMARY KEY,
    TraceId UNIQUEIDENTIFIER NOT NULL,
    Name NVARCHAR(255) NOT NULL,
    Status INT NOT NULL,
    StartTime DATETIME2 NOT NULL,
    EndTime DATETIME2 NULL,
    Attributes NVARCHAR(MAX) NULL,
    CreatedAt DATETIME2 NOT NULL
);
```

**After:**
```sql
CREATE TABLE Spans (
    Id UNIQUEIDENTIFIER PRIMARY KEY,
    TraceId UNIQUEIDENTIFIER NOT NULL,
    Name NVARCHAR(255) NOT NULL,
    Status INT NOT NULL,
    StartTime DATETIME2 NOT NULL,
    EndTime DATETIME2 NULL,
    Attributes NVARCHAR(MAX) NULL,
    CreatedAt DATETIME2 NOT NULL,
    UpdatedAt DATETIME2 NOT NULL  -- NEW
);

CREATE INDEX IX_Spans_UpdatedAt ON Spans(UpdatedAt);  -- NEW
```

## Monitoring

**Metrics to track:**
- Span upsert rate (inserts vs updates)
- Stale update rejection rate
- SignalR event emission latency
- Database query performance

**Logging:**
```csharp
_logger.LogInformation("Upserted {Count} spans, {Inserts} inserts, {Updates} updates",
    total, inserts, updates);
```

## Rollback Plan

If issues found:
1. Deploy previous version of API
2. Database rollback: `DROP INDEX IX_Spans_UpdatedAt; ALTER TABLE Spans DROP COLUMN UpdatedAt;`
3. Feature flag in frontend to disable real-time updates
