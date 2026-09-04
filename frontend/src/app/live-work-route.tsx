import { LiveMyWorkDataSource } from "../api/my-work-data-source";
import LiveWorkPage from "../pages/live-work-page";

const dataSource = new LiveMyWorkDataSource();

export default function LiveWorkRoute({
  navigate,
}: {
  navigate: (target: string) => void;
}): React.JSX.Element {
  return <LiveWorkPage dataSource={dataSource} navigate={navigate} />;
}
