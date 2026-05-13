import Link from "next/link";
import { getMembers } from "@/lib/org";

export default function MembersPage() {
  const members = getMembers();
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-amber-400">メンバー一覧</h1>
      <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
        {members.map((m) => (
          <Link key={m.name} href={`/members/${encodeURIComponent(m.name)}`}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-amber-500 transition-colors">
            <div className="text-lg font-bold text-white mb-1">{m.name}</div>
            <div className="text-xs text-gray-500">{m.skills.length} スキルファイル</div>
            {m.profile && (
              <p className="text-xs text-gray-400 mt-2 line-clamp-3 whitespace-pre-line">
                {m.profile.slice(0, 120)}…
              </p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
