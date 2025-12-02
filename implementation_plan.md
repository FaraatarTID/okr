# Implementation Plan - Personal OKR Tracking Panel

## Goal
Build a personal OKR tracking panel with a tree structure, including 2-year goals, strategies, quarterly objectives, key results, initiatives, and time tracking. The app will be local-first, persisting data to `localStorage`.

## User Review Required
> [!IMPORTANT]
> **Progress Calculation Strategy**:
> - **Manual**: User manually sets progress for every node.
> - **Automatic (Proposed)**: Parent progress is the average of its children's progress. Leaf nodes (Initiatives/Key Results) are manual.
> *Decision*: We will implement **Automatic** calculation for parents to reduce manual data entry.

> [!NOTE]
> **Time Tracking Location**:
> - Timer controls will be available on the **NodeItem** itself for quick access.
> - A global "Active Timer" floating indicator will show if a timer is running anywhere.

## Tech Stack
- **Framework**: React (Vite)
- **Styling**: TailwindCSS (for rapid, beautiful UI)
- **State Management**: Zustand (with `persist` middleware for local memory)
- **Icons**: Lucide React
- **Animations**: Framer Motion (for "wow" factor)
- **Drag & Drop**: `@hello-pangea/dnd` (for reordering nodes)
- **Utilities**: `clsx`, `tailwind-merge`

## Data Structure
We will use a hierarchical structure stored as a flat dictionary for easy lookups, with a recursive UI.

```typescript
type NodeType = 'goal' | 'strategy' | 'objective' | 'key_result' | 'initiative';

interface Node {
  id: string;
  type: NodeType;
  title: string;
  description?: string;
  progress: number; // 0-100
  children: string[]; // IDs of children
  parentId?: string;
  createdAt: number;
  
  // Time tracking specific
  timeSpent: number; // total accumulated minutes
  timerStartedAt?: number; // timestamp if currently running, undefined if stopped
  isExpanded: boolean; // UI state persisted
}

interface Store {
  nodes: Record<string, Node>;
  rootIds: string[]; // Top level (2-year goals)
  
  // Actions
  addNode: (parentId: string | null, type: NodeType, data: Partial<Node>) => void;
  updateNode: (id: string, data: Partial<Node>) => void;
  deleteNode: (id: string) => void;
  moveNode: (dragId: string, hoverId: string) => void; // Reordering
  
  // UI Actions
  toggleExpand: (id: string) => void;
  
  // Time Tracking Actions
  startTimer: (id: string) => void;
  stopTimer: (id: string) => void;
  tickTimer: () => void; // Called periodically to update UI if needed, or just calc on render
}
```

## Proposed Changes

### Phase 1: Setup
#### [NEW] [Project Initialization]
- Initialize Vite project: `npm create vite@latest . -- --template react-ts`
- Install dependencies: 
  ```bash
  npm install tailwindcss postcss autoprefixer zustand framer-motion lucide-react clsx tailwind-merge @hello-pangea/dnd date-fns
  ```
- Setup TailwindCSS configuration.

#### Expected File Structure
```
okr/
├── src/
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── OKRTree.tsx
│   │   ├── NodeItem.tsx
│   │   ├── AddNodeModal.tsx
│   │   ├── EditNodeModal.tsx
│   │   └── DeleteConfirmModal.tsx
│   ├── store/
│   │   └── useOKRStore.ts
│   ├── hooks/
│   │   └── useTimer.ts
│   ├── utils/
│   │   ├── cn.ts
│   │   └── formatTime.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── tailwind.config.js
├── postcss.config.js
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### Phase 2: Core Logic
#### [NEW] [store.ts](file:///src/store/useOKRStore.ts)
- Implement `useOKRStore` with Zustand.
- Add `persist` middleware.
- Implement `addNode`, `updateNode`, `deleteNode`.
- Implement `startTimer` / `stopTimer` logic.
- Implement `calculateProgress` helper (recursive up-propagation).

### Phase 3: UI Components
#### [NEW] [Layout](file:///src/components/Layout.tsx)
- Dark-themed, centered dashboard layout.
- Sidebar for "Active Timer" or quick stats.

#### [NEW] [OKRTree](file:///src/components/OKRTree.tsx)
- Recursive component to render the tree.
- Handle expansion/collapse animations.

#### [NEW] [NodeItem](file:///src/components/NodeItem.tsx)
- Distinct styles for each `NodeType` (e.g., Goals = large/bold, Initiatives = small/list-like).
- Inline editing for Title.
- Progress bar visualization.
- Play/Pause button for time tracking.

### Phase 4: Features
#### [NEW] [AddNodeModal](file:///src/components/AddNodeModal.tsx)
- Modal for creating new nodes
- Form with fields: title, description, type (auto-determined by parent)
- Validation

#### [NEW] [EditNodeModal](file:///src/components/EditNodeModal.tsx)
- Modal for editing existing nodes
- Inline editing for title, modal for description
- Progress slider (0-100)

#### [NEW] [DeleteConfirmModal](file:///src/components/DeleteConfirmModal.tsx)
- Confirmation dialog for deleting nodes
- Warning if node has children (cascade delete or prevent)

#### Drag & Drop Implementation
- Wrap tree in `DragDropContext` from `@hello-pangea/dnd`
- Make `NodeItem` draggable
- Allow reordering within same parent only (for MVP)

#### Time Tracking Logic
- `startTimer(id)`: Set `timerStartedAt = Date.now()`, stop all other timers
- `stopTimer(id)`: Add `(Date.now() - timerStartedAt) / 60000` to `timeSpent`, clear `timerStartedAt`
- Global timer indicator: Show which node is currently running

#### Progress Auto-Calculation
- When `updateNode` is called with progress change, trigger `recalculateProgress(parentId)`
- `recalculateProgress`: Average children's progress, update parent, recurse up

### Phase 5: Polish & Optimization
#### [NEW] [utils/cn.ts](file:///src/utils/cn.ts)
- Utility for merging Tailwind classes using `clsx` and `tailwind-merge`

#### [NEW] [utils/formatTime.ts](file:///src/utils/formatTime.ts)
- Format `timeSpent` (minutes) into human-readable format (e.g., "2h 30m")

#### [NEW] [hooks/useTimer.ts](file:///src/hooks/useTimer.ts)
- Custom hook to handle timer UI updates (re-render every second when timer is active)

#### Visual Polish
- Add smooth expand/collapse animations with Framer Motion
- Add fade-in animations when creating new nodes
- Add slide-out animations when deleting nodes
- Implement glassmorphism for cards
- Add hover effects and micro-interactions
- Ensure responsive design (mobile-friendly tree)

#### Edge Cases
- **Empty state**: Show helpful message when no goals exist
- **Deep nesting**: Add max depth warning or scroll optimization
- **Long titles**: Truncate with ellipsis, show full on hover
- **Concurrent timers**: Ensure only one timer runs (auto-stop previous)
- **Delete with children**: Offer cascade delete or prevent deletion

## Verification Plan

### Manual Verification

#### 1. CRUD Operations
- **Create**: 
  - Create a Root Goal (2-year goal)
  - Add a Strategy child to the Goal
  - Add an Objective child to the Strategy
  - Add a Key Result child to the Objective
  - Add an Initiative child to the Key Result
- **Read**: 
  - Verify all nodes display correctly in tree
  - Verify hierarchy is visually clear
- **Update**: 
  - Edit a node's title inline
  - Edit a node's description via modal
  - Update progress on a leaf node
- **Delete**: 
  - Delete a leaf node (Initiative) - should work immediately
  - Attempt to delete a node with children - should show warning
  - Cascade delete a Strategy with all children

#### 2. Persistence
- Create several nodes with various data
- Refresh the page
- Verify all nodes, progress, time spent, and expansion states persist

#### 3. Time Tracking
- Start timer on Initiative A
- Verify global timer indicator shows "Initiative A"
- Start timer on Initiative B
- Verify Initiative A timer stops automatically
- Verify only Initiative B timer is running
- Wait 1 minute
- Stop Initiative B timer
- Verify `timeSpent` increases by ~1 minute
- Verify time displays in human-readable format (e.g., "1m")

#### 4. Progress Calculation
- Create Goal → Strategy → Objective → Key Result → Initiative
- Set Initiative progress to 50%
- Verify Key Result auto-updates to 50%
- Add another Initiative under same Key Result, set to 100%
- Verify Key Result updates to 75% (average of 50% and 100%)
- Verify progress propagates up to Objective, Strategy, and Goal

#### 5. Drag & Drop
- Create multiple nodes at same level
- Drag and drop to reorder
- Verify order persists after refresh

#### 6. Visual Quality
- Verify dark theme looks premium
- Verify animations are smooth (expand/collapse, add/delete)
- Verify glassmorphism effects are applied
- Verify hover states and micro-interactions work
- Test on mobile viewport - ensure responsive

#### 7. Edge Cases
- **Empty State**: Delete all nodes, verify helpful empty message
- **Long Titles**: Create node with very long title, verify truncation
- **Deep Nesting**: Create 6+ levels deep, verify scroll/performance
- **Rapid Actions**: Rapidly create/delete nodes, verify no crashes

### Automated Tests (Optional, Time Permitting)
- Unit tests for store actions (`addNode`, `deleteNode`, `updateNode`)
- Unit tests for `calculateProgress` helper
- Unit tests for timer logic (`startTimer`, `stopTimer`)

