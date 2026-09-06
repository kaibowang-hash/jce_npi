import { useEffect, useId, useRef, useState } from "react";

import {
  LiveERPMasterDataSource,
  type ERPMasterDataSource,
  type ERPMasterKind,
  type ERPMasterPage,
  type ERPMasterRecord,
} from "../api/erp-master-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { useI18n } from "../i18n/runtime";
import { Button, TextInput } from "../ui-adapters/npi-ui";
import { isERPSourceId } from "../api/erp-source-id";
import { RequestFailurePanel } from "./problem-details-panel";
import "./erp-master-select.css";

const live = new LiveERPMasterDataSource();
type State =
  | { kind: "loading" }
  | {
      kind: "ready";
      page: ERPMasterPage;
      requestKey: string;
      checkedAt: number;
    }
  | { kind: "failed"; failure: RequestFailure };

export function ERPMasterSelect({
  kind,
  label,
  value,
  onChange,
  disabled = false,
  required = false,
  projectId,
  inputRef,
  dataSource = live,
}: {
  kind: ERPMasterKind;
  label: string;
  value: string;
  onChange: (record: ERPMasterRecord | null) => void;
  disabled?: boolean;
  required?: boolean;
  projectId?: string;
  inputRef?: (element: HTMLInputElement | null) => void;
  dataSource?: ERPMasterDataSource;
}): React.JSX.Element {
  const { t } = useI18n();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState(-1);
  const [state, setState] = useState<State>({ kind: "loading" });
  const [selected, setSelected] = useState<ERPMasterRecord | null>(null);
  const input = useRef<HTMLInputElement | null>(null);
  const requestKey = JSON.stringify([kind, query, offset, projectId]);
  useEffect(() => {
    if (!open || disabled) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void dataSource
        .load(kind, query, offset, controller.signal, projectId)
        .then((page) => {
          if (!controller.signal.aborted)
            setState({
              kind: "ready",
              page,
              requestKey,
              checkedAt: Date.now(),
            });
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted)
            setState({ kind: "failed", failure: toRequestFailure(error) });
        });
    }, 200);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    open,
    disabled,
    dataSource,
    kind,
    query,
    offset,
    attempt,
    projectId,
    requestKey,
  ]);
  const page =
    state.kind === "ready" && state.requestKey === requestKey
      ? state.page
      : null;
  const fresh =
    page !== null &&
    page.sourceVersion > 0 &&
    page.lastSynchronizedAt !== null &&
    (state.kind === "ready" ? state.checkedAt : 0) -
      Date.parse(page.lastSynchronizedAt) >=
      -300000 &&
    (state.kind === "ready" ? state.checkedAt : 0) -
      Date.parse(page.lastSynchronizedAt) <=
      24 * 60 * 60 * 1000;
  const items = page?.items ?? [];
  const choose = (item: ERPMasterRecord): void => {
    if (!fresh || !item.enabled || !isERPSourceId(item.sourceKey)) return;
    setSelected(item);
    onChange(item);
    setOpen(false);
    setQuery("");
    setOffset(0);
    setActive(-1);
    input.current?.focus();
  };
  const search = (text: string): void => {
    setQuery(text);
    setOffset(0);
    setActive(-1);
    setState({ kind: "loading" });
  };
  const begin = (): void => {
    if (!open) {
      search("");
      setOpen(true);
    }
  };
  return (
    <div
      className="erp-master-select"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false);
          setQuery("");
        }
      }}
    >
      <div className="erp-master-select__control">
        <TextInput
          aria-label={label}
          aria-autocomplete="list"
          aria-expanded={open && !disabled}
          aria-controls={`${id}-options`}
          aria-activedescendant={
            open && active >= 0 ? `${id}-option-${String(active)}` : undefined
          }
          autoComplete="off"
          disabled={disabled}
          required={required}
          role="combobox"
          ref={(element) => {
            input.current = element;
            inputRef?.(element);
          }}
          placeholder={t("Search ERPNext by code or name")}
          value={
            open
              ? query
              : selected?.sourceKey === value
                ? `${selected.sourceKey} — ${selected.displayName}`
                : value
          }
          maxLength={100}
          onChange={(event) => {
            search(event.currentTarget.value);
            setOpen(true);
            if (value) {
              setSelected(null);
              onChange(null);
            }
          }}
          onClick={begin}
          onKeyDown={(event) => {
            if (event.key === "Escape" && open) {
              event.preventDefault();
              event.stopPropagation();
              setOpen(false);
              return;
            }
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              if (!open) begin();
              else
                setActive((index) =>
                  Math.max(
                    0,
                    Math.min(
                      items.length - 1,
                      index + (event.key === "ArrowDown" ? 1 : -1),
                    ),
                  ),
                );
            }
            if (event.key === "Enter" && open) {
              event.preventDefault();
              const item = items[active];
              if (item) choose(item);
            }
          }}
        />
        <Button
          aria-label={t("Show ERPNext choices")}
          title={t("Show ERPNext choices")}
          disabled={disabled}
          icon="chevron"
          type="button"
          onClick={() => {
            if (open) setOpen(false);
            else begin();
            input.current?.focus();
          }}
        />
        {value && !required ? (
          <Button
            aria-label={t("Clear selection")}
            title={t("Clear selection")}
            disabled={disabled}
            icon="clear"
            type="button"
            onClick={() => {
              onChange(null);
              setSelected(null);
              setQuery("");
            }}
          />
        ) : null}
      </div>
      {open && !disabled ? (
        <div className="erp-master-select__popup">
          {state.kind === "loading" ? (
            <p role="status">{t("Loading ERPNext choices")}</p>
          ) : state.kind === "failed" ? (
            <>
              <RequestFailurePanel failure={state.failure} />
              <Button
                type="button"
                onClick={() => {
                  setState({ kind: "loading" });
                  setAttempt((n) => n + 1);
                }}
              >
                {t("Retry")}
              </Button>
            </>
          ) : !fresh ? (
            <p role="status">
              {t(
                "ERPNext choices are unavailable or out of date. Refresh after synchronization.",
              )}
            </p>
          ) : items.length === 0 ? (
            <p role="status">
              {t("No matching ERPNext records are available in this scope.")}
            </p>
          ) : null}
          <ul
            id={`${id}-options`}
            role="listbox"
            aria-label={label}
            className="erp-master-select__options"
          >
            {fresh
              ? items.map((item, index) => (
                  <li
                    key={item.sourceKey}
                    id={`${id}-option-${String(index)}`}
                    role="option"
                    aria-selected={item.sourceKey === value}
                    aria-disabled={
                      !item.enabled || !isERPSourceId(item.sourceKey)
                    }
                    className={
                      active === index ? "erp-master-select__active" : ""
                    }
                    onMouseDown={(event) => {
                      event.preventDefault();
                    }}
                    onClick={() => {
                      choose(item);
                    }}
                  >
                    <span data-language-exempt="business-data">
                      {item.sourceKey} — {item.displayName}
                    </span>
                    {item.parentKey ? (
                      <small data-language-exempt="business-data">
                        {item.parentKey}
                      </small>
                    ) : null}
                    {!item.enabled ? <small>{t("Disabled")}</small> : null}
                  </li>
                ))
              : null}
          </ul>
          {fresh && page.total > page.limit ? (
            <div className="erp-master-select__paging">
              <Button
                type="button"
                disabled={offset === 0}
                onClick={() => {
                  setOffset(Math.max(0, offset - 20));
                  setActive(-1);
                  setState({ kind: "loading" });
                }}
              >
                {t("Previous")}
              </Button>
              <Button
                type="button"
                disabled={offset + page.limit >= page.total}
                onClick={() => {
                  setOffset(offset + 20);
                  setActive(-1);
                  setState({ kind: "loading" });
                }}
              >
                {t("Next")}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
