import { getTickets } from "@/lib/org";

const STATUS_COLORS = {
  ToDo: "bg-gray-700 text-gray-300",
  Doing: "bg-blue-900 text-blue-300",
  Waiting: "bg-yellow-900 text-yellow-300",
  Done: "bg-green-900 text-green-300",
};

const PRIORITY_COLORS: Record<string, string> = {
  高: "text-red-400",
  中: "text-yellow-400",
  低: "text-gray-500",
};

export default function TicketsPage() {
  const tickets = getTickets();
  const statuses = ["ToDo", "Doing", "Waiting", "Done"] as const;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-amber-400">チケット管理</h1>

      {tickets.length === 0 ? (
        <p className="text-gray-500">チケットがまだありません。</p>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {statuses.map((status) => {
            const cols = tickets.filter((t) => t.status === status);
            return (
              <div key={status} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${STATUS_COLORS[status]}`}>
                    {status}
                  </span>
                  <span className="text-xs text-gray-600">{cols.length}</span>
                </div>
                <div className="space-y-2">
                  {cols.map((t) => (
                    <div key={t.id} className="bg-gray-800 rounded-lg p-3 border border-gray-700">
                      <div className="text-xs text-gray-500 mb-1">{t.id}</div>
                      <div className="text-sm text-gray-200 leading-snug">{t.title}</div>
                      <div className="flex items-center justify-between mt-2">
                        <span className={`text-xs font-medium ${PRIORITY_COLORS[t.priority] ?? "text-gray-400"}`}>
                          ▲ {t.priority}
                        </span>
                        <span className="text-xs text-gray-500">{t.assignee}</span>
                      </div>
                    </div>
                  ))}
                  {cols.length === 0 && (
                    <p className="text-xs text-gray-600 text-center py-4">なし</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
