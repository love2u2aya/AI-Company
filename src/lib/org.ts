import fs from "fs";
import path from "path";
import matter from "gray-matter";

const ROOT = process.cwd();

export interface Member {
  name: string;
  profile: string;
  skills: { name: string; content: string }[];
}

const MEMBER_DIRS = [
  "秘書", "Planner", "FP", "Critic", "Creator",
  "Editor", "Designer", "Slide_Designer", "SNS_Manager", "QC", "Video_Producer",
];

export function getMembers(): Member[] {
  return MEMBER_DIRS.map((name) => {
    const base = path.join(ROOT, "Organization", name);
    const profilePath = path.join(base, "Memory", "profile.md");
    const profile = fs.existsSync(profilePath)
      ? fs.readFileSync(profilePath, "utf-8")
      : "";

    const skillsDir = path.join(base, "Skills");
    const skills: { name: string; content: string }[] = [];
    if (fs.existsSync(skillsDir)) {
      fs.readdirSync(skillsDir)
        .filter((f) => f.endsWith(".md"))
        .forEach((f) => {
          skills.push({
            name: f.replace(".md", ""),
            content: fs.readFileSync(path.join(skillsDir, f), "utf-8"),
          });
        });
    }

    return { name, profile, skills };
  });
}

export function getMember(name: string): Member | undefined {
  return getMembers().find((m) => m.name === name);
}

export interface Ticket {
  id: string;
  title: string;
  status: "ToDo" | "Doing" | "Waiting" | "Done";
  priority: string;
  assignee: string;
  author: string;
  createdAt: string;
  content: string;
}

const STATUS_DIRS = ["ToDo", "Doing", "Waiting", "Done"] as const;

export function getTickets(): Ticket[] {
  const tickets: Ticket[] = [];
  const base = path.join(ROOT, "Workspace", "TicketManagement");

  for (const status of STATUS_DIRS) {
    const dir = path.join(base, status);
    if (!fs.existsSync(dir)) continue;
    fs.readdirSync(dir)
      .filter((f) => f.endsWith(".md"))
      .forEach((f) => {
        const raw = fs.readFileSync(path.join(dir, f), "utf-8");
        const { data, content } = matter(raw);
        const match = f.match(/^(TICKET-\d+)_(.+)\.md$/);
        tickets.push({
          id: match?.[1] ?? f,
          title: match?.[2] ?? f,
          status,
          priority: data["優先度"] ?? data.priority ?? "中",
          assignee: data["担当者"] ?? data.assignee ?? "—",
          author: data["作成者"] ?? data.author ?? "—",
          createdAt: data["作成日"] ?? data.createdAt ?? "",
          content,
        });
      });
  }
  return tickets;
}
