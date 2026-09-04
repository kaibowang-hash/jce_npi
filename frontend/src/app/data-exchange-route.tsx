import { LiveDataExchangeDataSource } from "../api/data-exchange-data-source";
import DataExchangeWorkspace from "../pages/data-exchange-workspace";

const dataSource = new LiveDataExchangeDataSource();

export default function DataExchangeRoute(): React.JSX.Element {
  return <DataExchangeWorkspace dataSource={dataSource} />;
}
