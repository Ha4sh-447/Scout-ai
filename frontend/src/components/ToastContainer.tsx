"use client";

import { useToast, Toast } from "@/lib/toast";
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  const getToastStyles = (type: Toast["type"]) => {
    switch (type) {
      case "success":
        return {
          bg: "bg-green-50 border-green-200",
          text: "text-green-900",
          icon: <CheckCircle className="w-5 h-5 text-green-600" />,
        };
      case "error":
        return {
          bg: "bg-red-50 border-red-200",
          text: "text-red-900",
          icon: <AlertCircle className="w-5 h-5 text-red-600" />,
        };
      case "warning":
        return {
          bg: "bg-yellow-50 border-yellow-200",
          text: "text-yellow-900",
          icon: <AlertTriangle className="w-5 h-5 text-yellow-600" />,
        };
      case "info":
      default:
        return {
          bg: "bg-blue-50 border-blue-200",
          text: "text-blue-900",
          icon: <Info className="w-5 h-5 text-blue-600" />,
        };
    }
  };

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-md pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => {
          const styles = getToastStyles(toast.type);
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, x: 400, y: -20 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              exit={{ opacity: 0, x: 400 }}
              transition={{ duration: 0.3 }}
              className={`${styles.bg} border rounded-lg p-4 flex items-start gap-3 shadow-lg pointer-events-auto`}
            >
              <div className="flex-shrink-0 mt-0.5">{styles.icon}</div>
              <div className="flex-1">
                <p className={`${styles.text} text-sm font-medium`}>
                  {toast.message}
                </p>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className={`flex-shrink-0 ${styles.text} hover:opacity-70 transition-opacity`}
              >
                <X className="w-5 h-5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
