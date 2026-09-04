import { useEffect, useRef, useState } from "react";

import type {
  GlobalSearchKind,
  GlobalSearchResponse,
  ReportingDataSource,
} from "../api/reporting-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { RequestFailurePanel } from "./problem-details-panel";
import { SemanticStatus, SourceSystemIdentity } from "./primitives";
import { useI18n } from "../i18n/runtime";
import { Button, Icon, TextInput } from "../ui-adapters/npi-ui";

type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: GlobalSearchResponse }
  | { kind: "failed"; failure: RequestFailure };

const searchKinds: readonly GlobalSearchKind[] = [
  "project",
  "customer",
  "part",
  "tooling",
  "document",
  "trial",
  "defect",
  "change",
  "file",
];

function kindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: GlobalSearchKind,
): string {
  switch (kind) {
    case "project":
      return t("Project");
    case "customer":
      return t("Customer");
    case "part":
      return t("Part");
    case "tooling":
      return t("Tooling");
    case "document":
      return t("Document");
    case "trial":
      return t("Trial");
    case "defect":
      return t("Defect");
    case "change":
      return t("Change");
    case "file":
      return t("File");
  }
}

export function GlobalSearchPanel({
  dataSource,
  navigate,
}: {
  dataSource: ReportingDataSource;
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  const request = useRef<AbortController | null>(null);
  const runSearch = (): void => {
    const normalized = query.trim();
    request.current?.abort();
    if (normalized.length < 2) {
      setOpen(true);
      setState({
        kind: "failed",
        failure: {
          kind: "request_not_ready",
          referenceId: `client-${globalThis.crypto.randomUUID()}`,
          referenceKind: "client",
        },
      });
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setOpen(true);
    setState({ kind: "loading" });
    void dataSource
      .search(normalized, searchKinds, { limit: 25 }, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setState({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setState({ kind: "failed", failure: toRequestFailure(error) });
      });
  };
  useEffect(() => () => request.current?.abort(), []);
  return (
    <div className="global-search-surface">
      <label className="global-search">
        <span className="visually-hidden">{t("Global search")}</span>
        <Icon name="search" />
        <TextInput
          aria-label={t("Global search")}
          onChange={(event) => {
            setQuery(event.currentTarget.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") runSearch();
            if (event.key === "Escape") setOpen(false);
          }}
          placeholder={t("Search projects, tools, trials, and drawings")}
          type="search"
          value={query}
        />
      </label>
      {open ? (
        <section
          aria-label={t("Global search results")}
          className="global-search-results"
          role="dialog"
        >
          <header className="global-search-results__header">
            <strong>{t("Global search results")}</strong>
            <Button
              aria-label={t("Close global search")}
              icon="clear"
              onClick={() => {
                setOpen(false);
              }}
              visual="ghost"
            />
          </header>
          {state.kind === "loading" ? (
            <p className="global-search-results__state" aria-busy="true">
              {t("Searching authorized objects")}
            </p>
          ) : state.kind === "failed" ? (
            <div className="global-search-results__state" role="alert">
              <p>
                {state.failure.kind === "request_not_ready"
                  ? t("Enter at least two search characters.")
                  : t("Global search is unavailable.")}
              </p>
              <RequestFailurePanel failure={state.failure} />
            </div>
          ) : state.kind === "loaded" ? (
            state.value.items.length ? (
              <ul className="global-search-results__list">
                {state.value.items.map((item) => (
                  <li
                    className="global-search-results__entry"
                    key={`${item.kind}:${item.globalId}`}
                  >
                    <button
                      className="global-search-results__item"
                      onClick={() => {
                        setOpen(false);
                        navigate(item.detailRoute);
                      }}
                      type="button"
                    >
                      <span className="global-search-results__item-copy">
                        <strong data-language-exempt="business-data">
                          {item.label}
                        </strong>
                        <small>
                          {kindLabel(t, item.kind)} ·{" "}
                          <SourceSystemIdentity
                            sourceSystem={item.sourceSystem}
                          />
                        </small>
                      </span>
                      <SemanticStatus
                        label={
                          item.availability === "available"
                            ? t("Available")
                            : item.availability === "stale"
                              ? t("Stale")
                              : item.availability === "partial"
                                ? t("Partial")
                                : t("Unavailable")
                        }
                        tone={
                          item.availability === "available"
                            ? "success"
                            : item.availability === "unavailable"
                              ? "danger"
                              : "warning"
                        }
                      />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="global-search-results__state">
                {t("No authorized object matches this query.")}
              </p>
            )
          ) : (
            <p className="global-search-results__state">
              {t("Enter a search term and press Enter.")}
            </p>
          )}
        </section>
      ) : null}
    </div>
  );
}
