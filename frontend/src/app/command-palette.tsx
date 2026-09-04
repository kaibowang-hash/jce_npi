import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { useI18n } from "../i18n/runtime";
import {
  focusControl,
  Icon,
  TextInput,
  type NpiIconName,
} from "../ui-adapters/npi-ui";

export interface ShellCommand {
  id: string;
  label: string;
  description: string;
  icon: NpiIconName;
  keywords: readonly string[];
  target?: string | undefined;
  unavailableReason?: string | undefined;
}

function commandMatches(command: ShellCommand, query: string): boolean {
  if (!query) return true;
  const searchable = [command.label, command.description, ...command.keywords]
    .join(" ")
    .toLocaleLowerCase();
  return searchable.includes(query.toLocaleLowerCase());
}

function isRestorableFocusTarget(
  target: HTMLElement | null | undefined,
): target is HTMLElement {
  return Boolean(
    target?.isConnected &&
    target !== document.body &&
    target !== document.documentElement,
  );
}

export function CommandPalette({
  commands,
  onClose,
  onOpen,
  onSelect,
  open,
  returnFocusTarget,
}: {
  commands: readonly ShellCommand[];
  onClose: () => void;
  onOpen: () => void;
  onSelect: (command: ShellCommand) => void;
  open: boolean;
  returnFocusTarget?: () => HTMLElement | null;
}): React.JSX.Element | null {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const filtered = useMemo(
    () => commands.filter((command) => commandMatches(command, query.trim())),
    [commands, query],
  );
  const closePalette = (): void => {
    setQuery("");
    onClose();
  };
  const selectCommand = (command: ShellCommand): void => {
    setQuery("");
    onSelect(command);
  };

  useEffect(() => {
    const handleShortcut = (event: globalThis.KeyboardEvent): void => {
      if (
        event.defaultPrevented ||
        event.altKey ||
        (!event.ctrlKey && !event.metaKey) ||
        event.key.toLocaleLowerCase() !== "k"
      ) {
        return;
      }
      event.preventDefault();
      const applicationRoot = document.querySelector<HTMLElement>("#root");
      const blockingDialog = document.querySelector<HTMLElement>(
        '[role="dialog"][aria-modal="true"]',
      );
      if (applicationRoot?.inert || blockingDialog) return;
      setQuery("");
      onOpen();
    };
    globalThis.addEventListener("keydown", handleShortcut);
    return () => {
      globalThis.removeEventListener("keydown", handleShortcut);
    };
  }, [onOpen]);

  useEffect(() => {
    if (!open) return undefined;
    const activeElement =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    restoreFocusRef.current = isRestorableFocusTarget(activeElement)
      ? activeElement
      : null;
    queueMicrotask(() => {
      void focusControl(searchRef.current);
    });
    return () => {
      const restoreTarget = restoreFocusRef.current;
      restoreFocusRef.current = null;
      queueMicrotask(() => {
        const preferredFallback = returnFocusTarget?.() ?? null;
        const mainContent = document.getElementById("main-content");
        const focusTarget = isRestorableFocusTarget(restoreTarget)
          ? restoreTarget
          : isRestorableFocusTarget(preferredFallback)
            ? preferredFallback
            : isRestorableFocusTarget(mainContent)
              ? mainContent
              : null;
        void focusControl(focusTarget);
      });
    };
  }, [open, returnFocusTarget]);

  if (!open) return null;

  const resultButtons = (): HTMLButtonElement[] =>
    Array.from(
      dialogRef.current?.querySelectorAll<HTMLButtonElement>(
        ".command-palette__result",
      ) ?? [],
    );
  const focusResult = (index: number): void => {
    const buttons = resultButtons();
    if (!buttons.length) return;
    const normalized = (index + buttons.length) % buttons.length;
    void focusControl(buttons[normalized] ?? null);
  };
  const handleResultKeyDown = (
    event: ReactKeyboardEvent<HTMLButtonElement>,
    index: number,
  ): void => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusResult(index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusResult(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusResult(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusResult(filtered.length - 1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closePalette();
    }
  };

  return (
    <div
      className="command-palette__backdrop"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) closePalette();
      }}
    >
      <div
        aria-label={t("Command palette")}
        aria-modal="true"
        className="command-palette"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            closePalette();
            return;
          }
          if (event.key !== "Tab") return;
          const focusable: HTMLElement[] = [];
          if (searchRef.current) focusable.push(searchRef.current);
          focusable.push(...resultButtons());
          if (!focusable.length) return;
          const currentIndex = focusable.indexOf(
            document.activeElement as HTMLElement,
          );
          const nextIndex = event.shiftKey
            ? currentIndex <= 0
              ? focusable.length - 1
              : currentIndex - 1
            : currentIndex >= focusable.length - 1
              ? 0
              : currentIndex + 1;
          event.preventDefault();
          void focusControl(focusable[nextIndex] ?? null);
        }}
        ref={dialogRef}
        role="dialog"
      >
        <header className="command-palette__header">
          <Icon name="keyboard" />
          <div>
            <h2>{t("Command palette")}</h2>
            <p>{t("Navigate approved workspaces with the keyboard.")}</p>
          </div>
          <kbd data-language-exempt="identifier">Esc</kbd>
        </header>
        <label className="command-palette__search">
          <span className="visually-hidden">{t("Search commands")}</span>
          <Icon name="search" />
          <TextInput
            aria-label={t("Search commands")}
            autoComplete="off"
            onChange={(event) => {
              setQuery(event.currentTarget.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                focusResult(0);
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                focusResult(filtered.length - 1);
              }
            }}
            placeholder={t("Type a workspace or action")}
            ref={searchRef}
            type="search"
            value={query}
          />
        </label>
        <ul
          aria-label={t("Command results")}
          className="command-palette__results"
        >
          {filtered.length ? (
            filtered.map((command, index) => {
              const available = Boolean(command.target);
              return (
                <li key={command.id}>
                  <button
                    aria-disabled={!available}
                    className="command-palette__result"
                    onClick={() => {
                      if (available) selectCommand(command);
                    }}
                    onKeyDown={(event) => {
                      handleResultKeyDown(event, index);
                    }}
                    type="button"
                  >
                    <Icon name={command.icon} />
                    <span>
                      <strong>{command.label}</strong>
                      <small>
                        {available
                          ? command.description
                          : command.unavailableReason}
                      </small>
                    </span>
                    {available ? (
                      <kbd data-language-exempt="identifier">Enter</kbd>
                    ) : (
                      <span className="command-palette__unavailable">
                        {t("Unavailable")}
                      </span>
                    )}
                  </button>
                </li>
              );
            })
          ) : (
            <li className="command-palette__empty" role="status">
              {t("No approved command matches this query.")}
            </li>
          )}
        </ul>
        <footer>
          <span>
            <kbd data-language-exempt="identifier">↑</kbd>
            <kbd data-language-exempt="identifier">↓</kbd> {t("Move")}
          </span>
          <span>
            <kbd data-language-exempt="identifier">Enter</kbd>{" "}
            {t("Open selected command")}
          </span>
          <span>
            <kbd data-language-exempt="identifier">Esc</kbd> {t("Close")}
          </span>
        </footer>
      </div>
    </div>
  );
}
