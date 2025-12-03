import { useState, useEffect } from "react";
import { Target } from "lucide-react";
import { Layout } from "./components/Layout";
import { OKRTree } from "./components/OKRTree";
import { AddNodeModal } from "./components/AddNodeModal";
import { InlineDeleteModal } from "./components/InlineDeleteModal";
import { GlobalTaskModal } from "./components/GlobalTaskModal";
import { useOKRStore } from "./store/useOKRStore";
import type { Node } from "./types";

function App() {
  const rootIds = useOKRStore((state) => state.rootIds);
  const deleteNodeStore = useOKRStore((state) => state.deleteNode);
  const getActiveTimer = useOKRStore((state) => state.getActiveTimer);
  const stopTimer = useOKRStore((state) => state.stopTimer);

  const importData = useOKRStore((state) => state.importData);

  // Handle browser close/refresh
  useEffect(() => {
    const handleBeforeUnload = () => {
      const activeNode = getActiveTimer();
      if (activeNode) {
        stopTimer(activeNode.id);
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [getActiveTimer, stopTimer]);

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [addParentId, setAddParentId] = useState<string | null>(null);

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [nodeToDelete, setNodeToDelete] = useState<Node | null>(null);

  const handleAddRoot = () => {
    setAddParentId(null);
    setIsAddModalOpen(true);
  };

  const handleAddChild = (parentId: string) => {
    setAddParentId(parentId);
    setIsAddModalOpen(true);
  };

  const handleCloseAddModal = () => {
    setIsAddModalOpen(false);
    setAddParentId(null);
  };

  const handleDelete = (node: Node) => {
    setNodeToDelete(node);
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setNodeToDelete(null);
  };

  const handleConfirmDelete = () => {
    if (nodeToDelete) {
      deleteNodeStore(nodeToDelete.id);
    }
  };

  const handleExport = () => {
    const state = useOKRStore.getState();
    const data = {
      nodes: state.nodes,
      rootIds: state.rootIds,
      version: 1,
      exportedAt: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `okr-backup-${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleImport = async (file: File) => {
    if (
      !window.confirm(
        "This will overwrite your current OKR data. Are you sure you want to proceed?"
      )
    ) {
      return;
    }

    try {
      const text = await file.text();
      const data = JSON.parse(text);

      if (!data.nodes || !data.rootIds) {
        alert("Invalid backup file format");
        return;
      }

      importData({
        nodes: data.nodes,
        rootIds: data.rootIds,
      });
      alert("Backup imported successfully");
    } catch (error) {
      console.error("Import failed:", error);
      alert("Failed to import backup file");
    }
  };

  return (
    <>
      <Layout
        onAddRoot={handleAddRoot}
        onExport={handleExport}
        onImport={handleImport}
      >
        {rootIds.length === 0 ? (
          // Empty State
          <div className="flex flex-col items-center justify-center py-20">
            <div className="node-card max-w-md text-center">
              <div className="inline-flex p-4 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 shadow-2xl mb-6">
                <Target className="w-12 h-12 text-white" />
              </div>

              <h2 className="text-3xl font-bold gradient-text mb-4">
                Welcome to OKR Tracker
              </h2>

              <p className="text-slate-300 mb-6 leading-relaxed">
                Start by creating your first 2-year goal. From there, you can
                build out your strategies, objectives, key results, and
                initiatives in a beautiful tree structure.
              </p>

              <div className="space-y-3 text-sm text-slate-400 mb-8">
                <div className="flex items-center gap-2 justify-center">
                  <div className="w-2 h-2 rounded-full bg-pink-500" />
                  <span>Track progress across all levels</span>
                </div>
                <div className="flex items-center gap-2 justify-center">
                  <div className="w-2 h-2 rounded-full bg-purple-500" />
                  <span>Time tracking for initiatives</span>
                </div>
                <div className="flex items-center gap-2 justify-center">
                  <div className="w-2 h-2 rounded-full bg-blue-500" />
                  <span>Automatic progress calculation</span>
                </div>
                <div className="flex items-center gap-2 justify-center">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span>Local storage - your data stays private</span>
                </div>
              </div>

              <button
                onClick={handleAddRoot}
                className="btn-primary text-lg px-8 py-3"
              >
                Create Your First Goal
              </button>
            </div>
          </div>
        ) : (
          // Tree View
          <div className="pb-12">
            <OKRTree
              nodeIds={rootIds}
              onAddChild={handleAddChild}
              onDelete={handleDelete}
            />
          </div>
        )}
      </Layout>

      {/* Modals */}
      <AddNodeModal
        isOpen={isAddModalOpen}
        onClose={handleCloseAddModal}
        parentId={addParentId}
      />

      <InlineDeleteModal
        isOpen={isDeleteModalOpen}
        onClose={handleCloseDeleteModal}
        onConfirm={handleConfirmDelete}
        nodeTitle={nodeToDelete?.title || ""}
        hasChildren={nodeToDelete ? nodeToDelete.children.length > 0 : false}
      />

      <GlobalTaskModal />
    </>
  );
}

export default App;
