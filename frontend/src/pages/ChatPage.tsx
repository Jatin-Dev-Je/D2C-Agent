import { ChatWindow } from "@/features/chat/components/ChatWindow";
import { useSessionStore } from "@/stores/session";
import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

export function ChatPage() {
  const { isAuthenticated } = useSessionStore();

  return (
    <div className="flex h-full flex-col">
      {!isAuthenticated && (
        <div className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/5 px-4 py-2.5">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
          <p className="text-xs text-amber-400">
            Set your bearer token in{" "}
            <Link to="/settings" className="underline underline-offset-2 hover:text-amber-300">
              Settings
            </Link>{" "}
            to enable chat.
          </p>
        </div>
      )}
      <div className="flex-1 overflow-hidden">
        <ChatWindow />
      </div>
    </div>
  );
}
