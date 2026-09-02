import { LiveGateReviewDataSource } from "../api/gate-review-data-source";
import GateEvidencePage from "../pages/gate-evidence-page";

const dataSource = new LiveGateReviewDataSource();

export default function LiveGateRoute({
  gateGlobalId,
  navigate,
  projectGlobalId,
}: {
  gateGlobalId: string;
  navigate: (target: string) => void;
  projectGlobalId: string;
}): React.JSX.Element {
  return (
    <GateEvidencePage
      dataSource={dataSource}
      gateGlobalId={gateGlobalId}
      navigate={navigate}
      projectGlobalId={projectGlobalId}
    />
  );
}
