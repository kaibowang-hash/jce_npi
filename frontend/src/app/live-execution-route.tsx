import { LiveIntegrationOperationsDataSource } from "../api/integration-operations-data-source";
import ExecutionPage from "../pages/execution-page";

const dataSource = new LiveIntegrationOperationsDataSource();

export default function LiveExecutionRoute({
  projectId,
}: {
  projectId: string;
}): React.JSX.Element {
  return <ExecutionPage dataSource={dataSource} projectId={projectId} />;
}
