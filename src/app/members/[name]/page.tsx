import { notFound } from "next/navigation";
import Link from "next/link";
import { getMembers, getMember } from "@/lib/org";

export async function generateStaticParams() {
  return getMembers().map((m) => ({ name: encodeURIComponent(m.name) }));
}

export default async function MemberPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const member = getMember(decodeURIComponent(name));
  if (!member) notFound();

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <Link href="/members" className="text-sm text-gray-500 hover:text-white">← メンバー一覧</Link>
      </div>
      <h1 className="text-2xl font-bold text-amber-400">{member.name}</h1>

      {member.profile && (
        <section className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">プロフィール</h2>
          <pre className="whitespace-pre-wrap text-sm text-gray-300 leading-relaxed font-sans">{member.profile}</pre>
        </section>
      )}

      {member.skills.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">スキル</h2>
          <div className="space-y-4">
            {member.skills.map((s) => (
              <details key={s.name} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <summary className="px-6 py-4 cursor-pointer text-sm font-medium text-gray-200 hover:text-white">
                  {s.name}
                </summary>
                <div className="px-6 pb-6 border-t border-gray-800 pt-4">
                  <pre className="whitespace-pre-wrap text-xs text-gray-400 leading-relaxed font-sans">{s.content}</pre>
                </div>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
