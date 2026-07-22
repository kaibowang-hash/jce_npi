import type { WorkItemViewModel } from "../domain/view-models";
import { PrototypeWorklistTransport } from "../api/worklist-data-source";
import { prototypeTimestamp, workItems } from "../fixtures/prototype";
import { formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { MetricStrip } from "../components/object-components";
import { Worklist } from "../components/worklist";

const worklistDataSource = new PrototypeWorklistTransport(workItems);

export default function WorkPage({
  navigate,
}: {
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const openItem = (item: WorkItemViewModel): void => {
    navigate(item.targetPath);
  };
  const prototypeDate = prototypeTimestamp.slice(0, 10);
  const overdue = workItems.filter(
    (item) => item.dueAt < prototypeTimestamp,
  ).length;
  const dueToday = workItems.filter((item) =>
    item.dueAt.startsWith(prototypeDate),
  ).length;
  const pendingApproval = workItems.filter(
    (item) => item.status === "pending_approval",
  ).length;
  const blocking = workItems.filter((item) => item.blocking).length;
  const integrationExceptions = workItems.filter(
    (item) => item.kind === "integration",
  ).length;
  return (
    <article className="page page--work">
      <header className="page-heading">
        <div>
          <h1>{t("My Work")}</h1>
          <p>
            {t(
              "One cross-object queue for assignments, blockers, decisions, and integration exceptions.",
            )}
          </p>
        </div>
      </header>
      <MetricStrip
        metrics={[
          {
            label: t("Overdue"),
            value: formatNumber(locale, overdue, 0),
            tone: "danger",
          },
          {
            label: t("Due today"),
            value: formatNumber(locale, dueToday, 0),
          },
          {
            label: t("Pending approval"),
            value: formatNumber(locale, pendingApproval, 0),
          },
          {
            label: t("Blocking"),
            value: formatNumber(locale, blocking, 0),
            tone: "warning",
          },
          {
            label: t("Integration exceptions"),
            value: formatNumber(locale, integrationExceptions, 0),
            tone: "danger",
          },
        ]}
      />
      <Worklist
        asOf={prototypeTimestamp}
        dataSource={worklistDataSource}
        onOpen={openItem}
      />
    </article>
  );
}
