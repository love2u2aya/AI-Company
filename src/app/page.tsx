import Link from "next/link";
import { getMembers, getTickets } from "@/lib/org";

export default function Home() {
  const members = getMembers();
  const tickets = getTickets();

  const counts = {
    ToDo: tickets.filter((t) => t.status === "ToDo").length,
    Doing: tickets.filter((t) => t.status === "Doing").length,
    Waiting: tickets.filter((t) => t.status === "Waiting").length,
    Done: tickets.filter((t) => t.status === "Done").length,
  };

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-3xl font-bold text-amber-400 mb-1">パパママ社</h1>
        <p className="text-gray-400">動画配信の広告収益で稼ぐ擬似会社 — エージェント組織ダッシュボード</p>
      </section>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {(["ToDo", "Doing", "Waiting", "Done"] as const).map((s) => (
          <Link key={s} href="/tickets" className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-amber-500 transition-colors">
            <div className="text-2xl font-bold text-white">{counts[s]}</div>
            <div className="text-sm text-gray-400 mt-1">{s}</div>
          </Link>
        ))}
      </section>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200">メンバー ({members.length}人)</h2>
          <Link href="/members" className="text-sm text-amber-400 hover:underline">すべて見る →</Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {members.map((m) => (
            <Link key={m.name} href={`/members/${encodeURIComponent(m.name)}`}
              className="bg-gray-900 border border-gray-800 rounded-lg p-3 hover:border-amber-500 transition-colors">
              <div className="font-medium text-sm">{m.name}</div>
              <div className="text-xs text-gray-500 mt-0.5">{m.skills.length} スキル</div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200">進行中チケット</h2>
          <Link href="/tickets" className="text-sm text-amber-400 hover:underline">すべて見る →</Link>
        </div>
        {tickets.filter((t) => t.status === "Doing").length === 0 ? (
          <p className="text-gray-500 text-sm">進行中のチケットはありません</p>
        ) : (
          <div className="space-y-2">
            {tickets.filter((t) => t.status === "Doing").map((t) => (
              <div key={t.id} className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center justify-between">
                <div>
                  <span className="text-xs text-gray-500 mr-2">{t.id}</span>
                  <span className="text-sm">{t.title}</span>
                </div>
                <span className="text-xs text-gray-400">{t.assignee}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
