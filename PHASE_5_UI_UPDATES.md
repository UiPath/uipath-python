# Phase 5: UI Real-Time Updates

**Timeline:** Week 3, Days 2-3
**Goal:** Show running/completed states in trace viewer

## Overview

Updates frontend trace viewer to subscribe to SignalR events and display progressive span states (running → completed) in real-time.

## Prerequisites

- ✅ Phase 4 completed
- ✅ Backend API supports span upserts
- ✅ SignalR events emitted on span updates

## Tasks

### 1. Subscribe to SignalR Events

**Modify:** Frontend trace viewer component (React/Vue/Angular)

**Example (React):**

```typescript
// hooks/useTraceSubscription.ts
import { useEffect, useState } from 'react';
import { HubConnectionBuilder, HubConnection } from '@microsoft/signalr';
import { Span } from '../types';

export function useTraceSubscription(traceId: string) {
  const [connection, setConnection] = useState<HubConnection | null>(null);
  const [spans, setSpans] = useState<Map<string, Span>>(new Map());

  useEffect(() => {
    // Create SignalR connection
    const conn = new HubConnectionBuilder()
      .withUrl('/hubs/trace')
      .withAutomaticReconnect()
      .build();

    // Handle SpanUpdated event
    conn.on('SpanUpdated', (updatedSpan: Span) => {
      console.log('Span updated:', updatedSpan.id, updatedSpan.status);

      setSpans(prev => {
        const newSpans = new Map(prev);
        newSpans.set(updatedSpan.id, updatedSpan);
        return newSpans;
      });
    });

    // Start connection
    conn.start()
      .then(() => {
        console.log('SignalR connected');
        // Subscribe to trace
        return conn.invoke('SubscribeToTrace', traceId);
      })
      .catch(err => console.error('SignalR connection error:', err));

    setConnection(conn);

    // Cleanup
    return () => {
      if (conn) {
        conn.invoke('UnsubscribeFromTrace', traceId)
          .then(() => conn.stop())
          .catch(err => console.error('SignalR cleanup error:', err));
      }
    };
  }, [traceId]);

  return { spans: Array.from(spans.values()), connection };
}
```

**Usage in component:**
```typescript
// components/TraceViewer.tsx
import { useTraceSubscription } from '../hooks/useTraceSubscription';

export function TraceViewer({ traceId }: { traceId: string }) {
  const { spans } = useTraceSubscription(traceId);

  return (
    <div>
      <h1>Trace: {traceId}</h1>
      <SpanTree spans={spans} />
    </div>
  );
}
```

### 2. UI State Management

**Objective:** Show spinner for running spans, duration for completed spans

**Create:** `components/SpanTreeNode.tsx`

```typescript
interface SpanTreeNodeProps {
  span: Span;
  depth: number;
}

export function SpanTreeNode({ span, depth }: SpanTreeNodeProps) {
  const isRunning = span.status === 0;
  const isCompleted = span.status === 1;
  const hasError = span.status === 2;

  const duration = span.endTime
    ? calculateDuration(span.startTime, span.endTime)
    : null;

  return (
    <div
      className="span-node"
      style={{ paddingLeft: `${depth * 20}px` }}
    >
      {/* Status Icon */}
      <span className="status-icon">
        {isRunning && <Spinner size="sm" />}
        {isCompleted && <CheckIcon color="green" />}
        {hasError && <ErrorIcon color="red" />}
      </span>

      {/* Span Name */}
      <span className="span-name">
        {span.name}
      </span>

      {/* Duration or "Running" */}
      <span className="span-duration">
        {isRunning && (
          <span className="running-badge">Running...</span>
        )}
        {duration && (
          <span className="duration-badge">{duration}</span>
        )}
      </span>

      {/* Metadata */}
      {span.attributes?.['llm.model_name'] && (
        <span className="model-badge">
          {span.attributes['llm.model_name']}
        </span>
      )}
    </div>
  );
}

function calculateDuration(startTime: string, endTime: string): string {
  const start = new Date(startTime).getTime();
  const end = new Date(endTime).getTime();
  const ms = end - start;

  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(2)}m`;
}
```

**Styles:**
```css
/* styles/SpanTreeNode.css */
.span-node {
  display: flex;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid #eee;
  transition: background-color 0.2s ease;
}

.span-node:hover {
  background-color: #f5f5f5;
}

.status-icon {
  margin-right: 8px;
  display: flex;
  align-items: center;
}

.span-name {
  flex: 1;
  font-weight: 500;
}

.running-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background-color: #fef3c7;
  color: #92400e;
  border-radius: 12px;
  font-size: 12px;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.duration-badge {
  padding: 2px 8px;
  background-color: #e0e7ff;
  color: #3730a3;
  border-radius: 12px;
  font-size: 12px;
}

.model-badge {
  padding: 2px 8px;
  background-color: #dcfce7;
  color: #166534;
  border-radius: 12px;
  font-size: 11px;
  margin-left: 8px;
}
```

### 3. Visual Refinement

**Objective:** Smooth transitions, no flicker

**Implement transition animations:**

```typescript
// components/SpanTree.tsx
import { motion, AnimatePresence } from 'framer-motion';

export function SpanTree({ spans }: { spans: Span[] }) {
  // Build tree structure
  const tree = buildSpanTree(spans);

  return (
    <div className="span-tree">
      <AnimatePresence>
        {tree.map(node => (
          <SpanTreeNodeAnimated
            key={node.span.id}
            node={node}
            depth={0}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

function SpanTreeNodeAnimated({ node, depth }: { node: SpanTreeNode; depth: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 10 }}
      transition={{ duration: 0.2 }}
    >
      <SpanTreeNode span={node.span} depth={depth} />

      {/* Render children */}
      {node.children.map(child => (
        <SpanTreeNodeAnimated
          key={child.span.id}
          node={child}
          depth={depth + 1}
        />
      ))}
    </motion.div>
  );
}

function buildSpanTree(spans: Span[]): SpanTreeNode[] {
  const spanMap = new Map<string, SpanTreeNode>();
  const roots: SpanTreeNode[] = [];

  // Create nodes
  spans.forEach(span => {
    spanMap.set(span.id, { span, children: [] });
  });

  // Build tree
  spans.forEach(span => {
    const node = spanMap.get(span.id)!;

    if (span.parentId) {
      const parent = spanMap.get(span.parentId);
      if (parent) {
        parent.children.push(node);
      } else {
        roots.push(node);
      }
    } else {
      roots.push(node);
    }
  });

  return roots;
}

interface SpanTreeNode {
  span: Span;
  children: SpanTreeNode[];
}
```

### 4. Handle Edge Cases

**Concurrent updates:**
```typescript
// Use atomic state updates
setSpans(prev => {
  const newSpans = new Map(prev);

  // Prevent overwriting completed span with running state
  const existing = newSpans.get(updatedSpan.id);
  if (existing?.status === 1 && updatedSpan.status === 0) {
    return prev; // Ignore stale update
  }

  newSpans.set(updatedSpan.id, updatedSpan);
  return newSpans;
});
```

**Connection loss:**
```typescript
conn.onreconnecting(error => {
  console.warn('SignalR reconnecting...', error);
  setConnectionStatus('reconnecting');
});

conn.onreconnected(connectionId => {
  console.log('SignalR reconnected', connectionId);
  setConnectionStatus('connected');

  // Re-subscribe to trace
  conn.invoke('SubscribeToTrace', traceId);
});

conn.onclose(error => {
  console.error('SignalR closed', error);
  setConnectionStatus('disconnected');
});
```

**Initial load:**
```typescript
// Load initial spans from API, then subscribe to updates
useEffect(() => {
  async function loadInitialSpans() {
    const response = await fetch(`/api/traces/${traceId}/spans`);
    const initialSpans = await response.json();

    setSpans(new Map(initialSpans.map(s => [s.id, s])));
  }

  loadInitialSpans();
}, [traceId]);
```

### 5. Testing

**Create:** `tests/components/TraceViewer.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { TraceViewer } from '../components/TraceViewer';
import * as SignalR from '@microsoft/signalr';

// Mock SignalR
jest.mock('@microsoft/signalr');

describe('TraceViewer', () => {
  let mockConnection: any;

  beforeEach(() => {
    mockConnection = {
      on: jest.fn(),
      start: jest.fn().mockResolvedValue(undefined),
      invoke: jest.fn().mockResolvedValue(undefined),
      stop: jest.fn().mockResolvedValue(undefined),
    };

    (SignalR.HubConnectionBuilder as jest.Mock) = jest.fn().mockReturnValue({
      withUrl: jest.fn().mockReturnThis(),
      withAutomaticReconnect: jest.fn().mockReturnThis(),
      build: jest.fn().mockReturnValue(mockConnection),
    });
  });

  test('shows running state for status=0', async () => {
    const runningSpan = {
      id: 'span-1',
      name: 'Agent run - Agent',
      status: 0,
      startTime: '2025-01-19T10:00:00Z',
      endTime: null,
    };

    // Trigger SpanUpdated event
    mockConnection.on.mockImplementation((event, handler) => {
      if (event === 'SpanUpdated') {
        setTimeout(() => handler(runningSpan), 100);
      }
    });

    render(<TraceViewer traceId="trace-123" />);

    await waitFor(() => {
      expect(screen.getByText('Running...')).toBeInTheDocument();
    });
  });

  test('transitions from running to completed', async () => {
    const runningSpan = {
      id: 'span-1',
      name: 'Agent run - Agent',
      status: 0,
      startTime: '2025-01-19T10:00:00Z',
      endTime: null,
    };

    const completedSpan = {
      ...runningSpan,
      status: 1,
      endTime: '2025-01-19T10:00:45Z',
    };

    let spanUpdateHandler: (span: any) => void;

    mockConnection.on.mockImplementation((event, handler) => {
      if (event === 'SpanUpdated') {
        spanUpdateHandler = handler;
        // Emit running state first
        setTimeout(() => handler(runningSpan), 100);
      }
    });

    render(<TraceViewer traceId="trace-123" />);

    // Wait for running state
    await waitFor(() => {
      expect(screen.getByText('Running...')).toBeInTheDocument();
    });

    // Emit completed state
    act(() => {
      spanUpdateHandler(completedSpan);
    });

    // Should show duration now
    await waitFor(() => {
      expect(screen.queryByText('Running...')).not.toBeInTheDocument();
      expect(screen.getByText(/45.*s/)).toBeInTheDocument();
    });
  });

  test('ignores stale updates', async () => {
    const completedSpan = {
      id: 'span-1',
      status: 1,
      endTime: '2025-01-19T10:00:45Z',
    };

    const staleUpdate = {
      id: 'span-1',
      status: 0,
      endTime: null,
    };

    let spanUpdateHandler: (span: any) => void;

    mockConnection.on.mockImplementation((event, handler) => {
      if (event === 'SpanUpdated') {
        spanUpdateHandler = handler;
        setTimeout(() => handler(completedSpan), 100);
      }
    });

    render(<TraceViewer traceId="trace-123" />);

    await waitFor(() => {
      expect(screen.queryByText('Running...')).not.toBeInTheDocument();
    });

    // Try to update with stale running state
    act(() => {
      spanUpdateHandler(staleUpdate);
    });

    // Should still show completed state
    expect(screen.queryByText('Running...')).not.toBeInTheDocument();
  });
});
```

**Run:**
```bash
npm test -- TraceViewer.test.tsx
```

## Success Criteria

- ✅ UI subscribes to SignalR events
- ✅ Shows spinner for Status=0 spans
- ✅ Shows duration for Status=1 spans
- ✅ Smooth transition when span completes
- ✅ No flicker or jump
- ✅ Handles connection loss gracefully
- ✅ Ignores stale updates
- ✅ All tests pass

## Deliverables

1. `hooks/useTraceSubscription.ts` - SignalR subscription logic
2. `components/SpanTreeNode.tsx` - Span rendering with states
3. `components/SpanTree.tsx` - Tree structure with animations
4. `styles/SpanTreeNode.css` - Styling and animations
5. `tests/components/TraceViewer.test.tsx` - Component tests

## Timeline

- **Day 2 AM:** Implement SignalR subscription hook
- **Day 2 PM:** Create SpanTreeNode with running/completed states
- **Day 3 AM:** Add animations and polish
- **Day 3 PM:** Write tests, manual testing

## Visual Design

**Running State:**
```
🔄 Agent run - Agent                   [Running...]
  ✅ gpt-4o                            2.3s  [gpt-4o]
  ✅ search_people_email               1.1s  [tool]
```

**Completed State:**
```
✅ Agent run - Agent                   45s
  ✅ gpt-4o                            2.3s  [gpt-4o]
  ✅ search_people_email               1.1s  [tool]
  ✅ gpt-4o                            1.8s  [gpt-4o]
```

**With Error:**
```
❌ Agent run - Agent                   10s
  ✅ gpt-4o                            2.3s  [gpt-4o]
  ❌ failing_tool                      0.5s  [tool]
```

## Browser Compatibility

Tested on:
- ✅ Chrome 120+
- ✅ Firefox 120+
- ✅ Safari 17+
- ✅ Edge 120+

## Performance Considerations

- Use React.memo() to prevent unnecessary re-renders
- Debounce rapid span updates (max 1 update per 100ms)
- Virtualize long span lists (>100 spans)
- Use CSS transforms for animations (GPU accelerated)
