# OKR Tracker - Feature Updates

## Changes Made

### 1. Time Tracking - Initiatives Only
- **Timer controls are now only visible for initiatives**
- Timer button (Play/Pause) only appears in the actions menu for initiative nodes
- Time tracking display only shows for initiatives that have tracked time
- All other node types (goals, strategies, objectives, key results) no longer show timer controls

### 2. Star Rating for Key Results
- **Key results now use a 1-5 star rating system instead of progress bars**
- Users can click on stars to rate key results from 1 to 5 stars
- Stars light up in yellow when selected
- Hover effects provide visual feedback
- Accessible with proper aria-labels for screen readers

### Implementation Details

#### Type Definitions (`src/types/index.ts`)
- Added `rating?: number` field to the `Node` interface
- Rating ranges from 0-5, where 0 means not rated

#### Store (`src/store/useOKRStore.ts`)
- New nodes are initialized with `rating: 0`
- Rating is persisted in local storage along with other node data

#### Node Display (`src/components/NodeItem.tsx`)
- **Conditional rendering for key results**: Shows star rating instead of progress bar
- **Conditional rendering for initiatives**: Only initiatives show timer controls
- Star rating is interactive - clicking a star sets the rating
- Timer controls (Play/Pause button) only appear for initiative nodes
- Time tracking display only shows for initiatives with tracked time

#### Edit Modal (`src/components/EditNodeModal.tsx`)
- **Conditional form fields**:
  - Key results: Shows star rating selector (larger stars for easier clicking)
  - Other node types: Shows progress slider (0-100%)
- Updates are saved based on node type (rating for key results, progress for others)

## User Experience

### For Key Results
1. View the current rating as lit-up yellow stars
2. Click any star (1-5) to set a new rating
3. Edit modal provides a larger star interface for easier selection

### For Initiatives
1. Timer controls appear on hover in the actions menu
2. Click Play to start tracking time
3. Click Pause to stop tracking time
4. Time spent is displayed below the node when > 0
5. Only one timer can run at a time across all initiatives

### For Other Node Types
- Goals, Strategies, and Objectives continue to use the progress bar (0-100%)
- No timer controls are shown
- Progress can be updated via the edit modal

## Technical Notes
- All changes are backward compatible with existing data
- Existing nodes will have `rating: 0` by default
- Star ratings use the Lucide React `Star` icon component
- Accessibility: All star buttons include proper `aria-label` attributes
