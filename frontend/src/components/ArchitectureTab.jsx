import { useEffect, useState } from "react";
import { apiGet } from "../lib/api.js";
import { useI18n } from "../i18n/LanguageContext.jsx";

// key: /api/system field, cloud: value meaning the Huawei Cloud service is in use
const SERVICES = [
  { id: "rds", key: "database", cloud: "mysql", name: "RDS for MySQL" },
  { id: "dcs", key: "cache", cloud: "redis", name: "DCS for Redis" },
  { id: "obs", key: "storage", cloud: "obs", name: "OBS" },
  { id: "modelarts", key: "predictor", cloud: "modelarts", name: "ModelArts" },
  { id: "pangu", key: "assistant", cloud: "llm", name: "Pangu / LLM" },
];

function Box({ title, body, badge, active }) {
  return (
    <div
      className={`rounded-xl border-2 p-3 ${active ? "border-leaf bg-leaf-light" : "border-stone-300 bg-white"}`}
    >
      <p className="font-bold">{title}</p>
      <p className="text-sm text-stone-700">{body}</p>
      {badge && (
        <p className="mt-1 text-xs font-semibold text-stone-600">{badge}</p>
      )}
    </div>
  );
}

const Arrow = () => (
  <div className="flex justify-center text-2xl text-leaf" aria-hidden="true">
    ↓
  </div>
);

export default function ArchitectureTab() {
  const { t } = useI18n();
  const [sys, setSys] = useState(null);

  useEffect(() => {
    apiGet("/api/system")
      .then(setSys)
      .catch(() => setSys(null));
  }, []);

  const badge = (s) => {
    if (!sys) return null;
    return sys[s.key] === s.cloud
      ? t("archActiveCloud")
      : t("archActiveLocal", { value: sys[s.key] });
  };

  return (
    <section className="card space-y-4">
      <div>
        <h2 className="text-xl font-bold">{t("tabArch")}</h2>
        <p className="text-stone-600">{t("archIntro")}</p>
      </div>
      <div className="grid gap-3">
        <Box title={t("archUsers")} body={t("archUsersBody")} />
        <Arrow />
        <Box
          title="ECS"
          body={t("archEcsBody")}
          badge={sys && (sys.scheduler ? t("archScheduler") : null)}
          active
        />
        <Arrow />
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {SERVICES.map((s) => (
            <Box
              key={s.id}
              title={s.name}
              body={t(`arch_${s.id}`)}
              badge={badge(s)}
              active={sys?.[s.key] === s.cloud}
            />
          ))}
        </div>
        <Box title="Open-Meteo" body={t("archWeatherBody")} />
      </div>
      <div>
        <h3 className="font-bold">{t("archFlowTitle")}</h3>
        <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <li key={n}>{t(`archFlow${n}`)}</li>
          ))}
        </ol>
      </div>
      <p className="text-xs text-stone-500">{t("archLegend")}</p>
    </section>
  );
}
