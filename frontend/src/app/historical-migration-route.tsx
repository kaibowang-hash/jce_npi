import { LiveHistoricalMigrationDataSource } from "../api/historical-migration-data-source";
import HistoricalMigrationWorkspace from "../pages/historical-migration-workspace";

const dataSource = new LiveHistoricalMigrationDataSource();

export default function HistoricalMigrationRoute(): React.JSX.Element {
  return <HistoricalMigrationWorkspace dataSource={dataSource} />;
}
