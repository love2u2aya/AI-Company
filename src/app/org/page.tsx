import Link from "next/link";

const ORG_CHART = [
  { role: "社長", desc: "指示・意思決定", level: 0 },
  { role: "秘書", desc: "タスク化・全体コーディネート", level: 1 },
  { role: "Planner", desc: "トレンド調査・企画", level: 2 },
  { role: "FP", desc: "金融正確性・深層洞察", level: 2 },
  { role: "Critic", desc: "企画批評・品質ゲート", level: 2 },
  { role: "Creator", desc: "ナレーション原稿・音声収録", level: 2 },
  { role: "Editor", desc: "カット・テロップ・BGM", level: 2 },
  { role: "Designer", desc: "サムネイル・グラフィック", level: 2 },
  { role: "Slide_Designer", desc: "動画内スライド専任", level: 2 },
  { role: "SNS_Manager", desc: "投稿・分析・スポンサー対応", level: 2 },
  { role: "QC", desc: "品質管理・アップロード許可証", level: 2 },
  { role: "Video_Producer", desc: "MP4生成（音声合成＋合成）", level: 2 },
];

export default function OrgPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-amber-400">組織図</h1>

      <div className="space-y-4">
        {[0, 1, 2].map((level) => {
          const nodes = ORG_CHART.filter((n) => n.level === level);
          return (
            <div key={level}>
              {level > 0 && (
                <div className="flex justify-center my-2">
                  <div className="w-px h-6 bg-gray-700" />
                </div>
              )}
              <div className={`flex flex-wrap justify-center gap-3`}>
                {nodes.map((n) => (
                  <Link
                    key={n.role}
                    href={n.role === "社長" ? "#" : `/members/${encodeURIComponent(n.role)}`}
                    className={`rounded-xl border px-5 py-3 text-center transition-colors
                      ${level === 0
                        ? "bg-amber-500/20 border-amber-500 text-amber-300 font-bold"
                        : level === 1
                        ? "bg-gray-800 border-gray-600 text-gray-100 font-semibold"
                        : "bg-gray-900 border-gray-700 text-gray-300 hover:border-amber-500"
                      }`}
                  >
                    <div className="text-sm font-semibold">{n.role}</div>
                    <div className="text-xs text-gray-500 mt-0.5 max-w-[160px]">{n.desc}</div>
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-gray-200 mb-3">動画1本の制作フロー</h2>
        <ol className="space-y-2 text-sm text-gray-400">
          {[
            ["Planner", "トレンド調査 → 企画案作成"],
            ["FP", "金融正確性・深み付与"],
            ["Critic", "企画批評・品質ゲート通過"],
            ["Creator", "ナレーション原稿・音声収録"],
            ["Slide_Designer", "動画内スライド制作"],
            ["Video_Producer", "MP4生成（音声＋スライド合成）"],
            ["Designer", "サムネイル制作"],
            ["Editor", "カット編集・テロップ・BGM"],
            ["QC", "品質チェック → アップロード許可証発行"],
            ["SNS_Manager", "YouTube非公開アップロード → 公開"],
          ].map(([role, step], i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="shrink-0 w-6 h-6 rounded-full bg-gray-800 border border-gray-700 text-center text-xs leading-6 text-gray-400">{i + 1}</span>
              <span>
                <span className="text-amber-400 font-medium">{role}</span>
                <span className="text-gray-500 mx-2">—</span>
                {step}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
