import { useEffect, useId, type PropsWithChildren } from "react";

import { useI18n } from "../i18n/runtime";

export type DisplayBrandAssetContext =
  | "company-footer"
  | "entry-loading"
  | "erp-source"
  | "favicon"
  | "platform-source"
  | "wordmark-dark"
  | "wordmark-light";

interface DisplayBrandAsset {
  readonly documentName: string;
  readonly url: string;
}

const platformIcon: DisplayBrandAsset = Object.freeze({
  documentName: "LaunchFlow Icon.svg",
  url: new URL(
    "../../../docs/Brand Asset/LaunchFlow Icon.svg?no-inline",
    import.meta.url,
  ).href,
});

export const displayBrandAssets: Readonly<
  Record<DisplayBrandAssetContext, DisplayBrandAsset>
> = Object.freeze({
  "company-footer": Object.freeze({
    documentName: "Company LOGO.svg",
    url: new URL(
      "../../../docs/Brand Asset/Company LOGO.svg?no-inline",
      import.meta.url,
    ).href,
  }),
  "entry-loading": Object.freeze({
    documentName: "Loading.svg",
    url: new URL(
      "../../../docs/Brand Asset/Loading.svg?no-inline",
      import.meta.url,
    ).href,
  }),
  "erp-source": Object.freeze({
    documentName: "Core.png",
    url: new URL(
      "../../../docs/Brand Asset/Core.png?no-inline",
      import.meta.url,
    ).href,
  }),
  favicon: platformIcon,
  "platform-source": platformIcon,
  "wordmark-dark": Object.freeze({
    documentName: "LaunchFlow-logo_White.svg",
    url: new URL(
      "../../../docs/Brand Asset/LaunchFlow-logo_White.svg?no-inline",
      import.meta.url,
    ).href,
  }),
  "wordmark-light": Object.freeze({
    documentName: "LaunchFlow-logo_Standard.svg",
    url: new URL(
      "../../../docs/Brand Asset/LaunchFlow-logo_Standard.svg?no-inline",
      import.meta.url,
    ).href,
  }),
});

function BrandImage({
  accessibleName,
  className,
  context,
  decorative = false,
  translatedTooltip = false,
  wideTooltipAnchor = false,
}: {
  accessibleName: string;
  className: string;
  context: Exclude<DisplayBrandAssetContext, "favicon">;
  decorative?: boolean;
  translatedTooltip?: boolean;
  wideTooltipAnchor?: boolean;
}): React.JSX.Element {
  const asset = displayBrandAssets[context];
  const tooltipId = useId();
  const image = (
    <img
      alt={decorative ? "" : accessibleName}
      aria-describedby={translatedTooltip ? tooltipId : undefined}
      aria-hidden={decorative ? "true" : undefined}
      className={className}
      data-brand-asset={asset.documentName}
      data-brand-context={context}
      draggable="false"
      src={asset.url}
      tabIndex={translatedTooltip ? 0 : undefined}
    />
  );
  if (!translatedTooltip) return image;
  return (
    <span
      className={`display-brand__tooltip-anchor${wideTooltipAnchor ? " display-brand__tooltip-anchor--wide" : ""}`}
    >
      {image}
      <span className="display-brand__tooltip" id={tooltipId} role="tooltip">
        {accessibleName}
      </span>
    </span>
  );
}

export function DisplayBrandWordmark({
  accessibleName,
  decorative = false,
  surface,
}: {
  accessibleName: string;
  decorative?: boolean;
  surface: "dark" | "light";
}): React.JSX.Element {
  return (
    <BrandImage
      accessibleName={accessibleName}
      className="display-brand__wordmark"
      context={surface === "dark" ? "wordmark-dark" : "wordmark-light"}
      decorative={decorative}
    />
  );
}

export function DisplayBrandPlatformIcon({
  accessibleName,
  decorative = false,
}: {
  accessibleName: string;
  decorative?: boolean;
}): React.JSX.Element {
  return (
    <BrandImage
      accessibleName={accessibleName}
      className="display-brand__platform-icon"
      context="platform-source"
      decorative={decorative}
      translatedTooltip={!decorative}
    />
  );
}

export function DisplayBrandErpIdentity({
  accessibleName,
}: {
  accessibleName: string;
}): React.JSX.Element {
  return (
    <BrandImage
      accessibleName={accessibleName}
      className="display-brand__erp-identity"
      context="erp-source"
      translatedTooltip
      wideTooltipAnchor
    />
  );
}

export function DisplayBrandCompanyMark({
  accessibleName,
}: {
  accessibleName: string;
}): React.JSX.Element {
  return (
    <BrandImage
      accessibleName={accessibleName}
      className="display-brand__company-mark"
      context="company-footer"
    />
  );
}

export function applyDisplayBrandDocument(
  documentReference: Document,
  title: string,
): HTMLLinkElement {
  documentReference.title = title;
  let favicon =
    documentReference.head.querySelector<HTMLLinkElement>('link[rel~="icon"]');
  if (!favicon) {
    favicon = documentReference.createElement("link");
    favicon.rel = "icon";
    documentReference.head.append(favicon);
  }
  const asset = displayBrandAssets.favicon;
  favicon.type = "image/svg+xml";
  favicon.href = asset.url;
  favicon.dataset.brandAsset = asset.documentName;
  favicon.dataset.brandContext = "favicon";
  return favicon;
}

export function DisplayBrandBootstrap({
  children,
}: PropsWithChildren): React.JSX.Element {
  const { isLocalizationBootstrapping, t } = useI18n();
  const productName = t("LaunchFlow");

  useEffect(() => {
    applyDisplayBrandDocument(document, productName);
  }, [productName]);

  if (isLocalizationBootstrapping) {
    const accessibleName = t("Loading LaunchFlow");
    return (
      <div
        aria-busy="true"
        aria-label={accessibleName}
        className="display-brand__entry-loading"
        role="status"
      >
        <BrandImage
          accessibleName={accessibleName}
          className="display-brand__loading-mark"
          context="entry-loading"
          decorative
        />
        <span className="display-brand__loading-label">{accessibleName}</span>
      </div>
    );
  }

  return <>{children}</>;
}
