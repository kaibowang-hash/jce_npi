import type { MyWorkDataSource } from "../api/my-work-data-source";
import { LiveMyWorklist } from "../components/live-my-worklist";
import { useI18n } from "../i18n/runtime";

export default function LiveWorkPage({
  dataSource,
  navigate,
}: {
  dataSource: MyWorkDataSource;
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <article className="page page--work">
      <header className="page-heading">
        <div>
          <h1>{t("My Work")}</h1>
          <p>
            {t(
              "Current-user queue for owned work, Gate reviews, blockers, risks, issues, and decisions.",
            )}
          </p>
        </div>
      </header>
      <LiveMyWorklist dataSource={dataSource} navigate={navigate} />
    </article>
  );
}
