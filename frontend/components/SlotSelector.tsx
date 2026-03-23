"use client";

interface Slot {
  start: string;
  end: string;
  conflicts: string[];
  score: number;
}

interface SlotSelectorProps {
  slots: Slot[];
  onSelect: (slot: Slot) => void;
}

export default function SlotSelector({ slots, onSelect }: SlotSelectorProps) {
  if (slots.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No available slots found.</p>
      </div>
    );
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-300 mb-2">📅 Select a Meeting Slot</h3>
      {slots.map((slot, index) => (
        <button
          key={index}
          onClick={() => onSelect(slot)}
          className="w-full text-left rounded-xl border border-white/10 bg-gray-800/50 hover:bg-gray-700/60 p-4 transition-all duration-200 hover:border-blue-500/50 group"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-white group-hover:text-blue-300 transition-colors">
                {formatDate(slot.start)}
              </p>
              <p className="text-sm text-gray-400">
                {formatTime(slot.start)} – {formatTime(slot.end)}
              </p>
            </div>
            <div className="text-right">
              {slot.conflicts.length === 0 ? (
                <span className="text-xs font-medium text-emerald-400 bg-emerald-900/30 px-2 py-1 rounded-full">
                  ✓ All available
                </span>
              ) : (
                <span className="text-xs font-medium text-amber-400 bg-amber-900/30 px-2 py-1 rounded-full">
                  {slot.conflicts.length} conflict{slot.conflicts.length > 1 ? "s" : ""}
                </span>
              )}
            </div>
          </div>
          {slot.conflicts.length > 0 && (
            <p className="text-xs text-gray-500 mt-2">
              Conflicts: {slot.conflicts.join(", ")}
            </p>
          )}
        </button>
      ))}
    </div>
  );
}
