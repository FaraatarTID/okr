export type NodeType =
  | "goal"
  | "strategy"
  | "objective"
  | "key_result"
  | "initiative"
  | "task";

export interface Node {
  id: string;
  type: NodeType;
  title: string;
  description?: string;
  progress: number; // 0-100 (only used for calculations, not displayed)
  children: string[]; // IDs of children
  parentId?: string;
  createdAt: number;

  // Time tracking specific (only for initiatives and tasks)
  timeSpent: number; // total accumulated minutes
  timerStartedAt?: number; // timestamp if currently running, undefined if stopped
  lastSessionTime?: number; // minutes from the last completed session
  isExpanded: boolean; // UI state persisted

  // Rating for key results (1-5 stars)
  rating?: number; // 0-5, where 0 means not rated

  // Gemini Analysis
  geminiScore?: number; // 0-100
  geminiAnalysis?: string;
}

export interface OKRStore {
  nodes: Record<string, Node>;
  rootIds: string[]; // Top level (2-year goals)

  // Actions
  addNode: (
    parentId: string | null,
    type: NodeType,
    data: Partial<Node>
  ) => void;
  updateNode: (id: string, data: Partial<Node>) => void;
  deleteNode: (id: string) => void;
  moveNode: (dragId: string, parentId: string | null, newIndex: number) => void; // Reordering
  updateGeminiAnalysis: (id: string, score: number, analysis: string) => void;

  // UI Actions
  toggleExpand: (id: string) => void;

  // Time Tracking Actions
  startTimer: (id: string) => void;
  stopTimer: (id: string) => void;
  getActiveTimer: () => Node | null;

  // Modal State
  activeTaskModalNodeId: string | null;
  setActiveTaskModalNodeId: (id: string | null) => void;

  // Data Management
  importData: (data: {
    nodes: Record<string, Node>;
    rootIds: string[];
  }) => void;
}
