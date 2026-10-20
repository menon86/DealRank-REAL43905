import { useEffect, useState } from "react";
import * as client from "../lib/client";
import { formatMoney, formatPercent } from "../lib/format";
import type { DealOut, GeographyOut, RentCheckOut, RentCheckStatus } from "../lib/types";

interface MarketCheckViewProps {
  deals: DealOut[];
}

const STATUS_LABELS: Record<RentCheckStatus, string> = {
  ok: "In line with market",
  caution: "Differs from market",
  flag: "Far from market",
  not_comparable: "Not comparable",
  no_data: "No market data",
};

const SOURCE_LABELS: Record<string, string> = {
  zillow_zori: "Zillow ZORI",
  apartment_list: "Apartment List",
};

/** Prefer a per-unit deal: per-bed rents can't be compared with whole-unit indexes. */
function defaultDealId(deals: DealOut[]): string {
  return (deals.find((d) => d.leasing_mode === "per_unit") ?? deals[0])?.id ?? "";
}

export function MarketCheckView({ deals }: MarketCheckViewProps) {
  const [dealId, setDealId] = useState(defaultDealId(deals));
  const [geographies, setGeographies] = useState<GeographyOut[]>([]);
  const [geography, setGeography] = useState("");
  const [result, setResult] = useState<RentCheckOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadSource, setUploadSource] = useState<"zillow_zori" | "apartment_list">("zillow_zori");
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  function loadGeographies() {
    return client
      .listGeographies()
      .then((g) => {
        setGeographies(g);
        if (g.length > 0) setGeography((prev) => prev || g[0].geography);
      })
      .catch((err) => setError(client.describeError(err)));
  }

  useEffect(() => {
    void loadGeographies();
  }, []);

  async function handleUpload(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setUploadMessage(null);
    setUploadError(null);
    try {
      const result = await client.uploadMarketRents(uploadSource, await file.text());
      setUploadMessage(
        `Loaded ${result.geographies.toLocaleString()} geographies ` +
          `(${result.inserted.toLocaleString()} new rows, ${result.updated.toLocaleString()} updated).`,
      );
      await loadGeographies();
    } catch (err) {
      setUploadError(`Upload failed. ${client.describeError(err)}`);
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    if (!dealId && deals.length > 0) setDealId(defaultDealId(deals));
  }, [deals, dealId]);

  useEffect(() => setResult(null), [dealId, geography]);

  async function runCheck() {
    setLoading(true);
    setError(null);
    try {
      setResult(await client.rentCheck(dealId, geography.trim()));
    } catch (err) {
      setError(client.describeError(err));
    } finally {
      setLoading(false);
    }
  }

  const uniqueGeographies = Array.from(new Set(geographies.map((g) => g.geography)));

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>Market rent sanity check</h2>
          <p className="card-subtitle">
            Compares a deal&apos;s per-unit rent with Zillow ZORI / Apartment List market medians
            loaded from CSV. A check, not a valuation: it tells you when an underwritten rent is far
            from what the market data shows.
          </p>
        </div>
      </div>

      {deals.length === 0 ? (
        <div className="empty-state">Add a deal on the Deals tab first.</div>
      ) : (
        <>
          {geographies.length === 0 && (
            <div className="status-banner info" role="status">
              No market rent data is loaded yet. Download a Zillow ZORI or Apartment List CSV and
              upload it below.
            </div>
          )}
          <div className="control-grid">
            <div className="field">
              <label htmlFor="mr-source">Rent data source</label>
              <select
                id="mr-source"
                value={uploadSource}
                onChange={(e) => setUploadSource(e.target.value as typeof uploadSource)}
              >
                <option value="zillow_zori">Zillow ZORI (CSV)</option>
                <option value="apartment_list">Apartment List (CSV)</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="mr-file">
                {geographies.length > 0 ? "Refresh data" : "Load data"}
              </label>
              <input
                id="mr-file"
                type="file"
                accept=".csv,text/csv"
                disabled={uploading}
                onChange={(e) => {
                  void handleUpload(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </div>
          </div>
          {uploading && (
            <span className="inline-status" role="status">
              <span className="spinner" aria-hidden="true" /> Loading rent data…
            </span>
          )}
          {uploadMessage && (
            <div className="status-banner info" role="status">
              {uploadMessage}
            </div>
          )}
          {uploadError && (
            <div className="status-banner error" role="alert">
              {uploadError}
            </div>
          )}
          <div className="control-grid">
            <div className="field">
              <label htmlFor="mc-deal">Deal</label>
              <select id="mc-deal" value={dealId} onChange={(e) => setDealId(e.target.value)}>
                {deals.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="mc-geo">Geography</label>
              <input
                id="mc-geo"
                list="geo-options"
                value={geography}
                placeholder="e.g. Indianapolis, IN"
                onChange={(e) => setGeography(e.target.value)}
              />
              <datalist id="geo-options">
                {uniqueGeographies.map((g) => (
                  <option key={g} value={g} />
                ))}
              </datalist>
            </div>
            <div className="field">
              <span className="field-label">&nbsp;</span>
              <button
                type="button"
                className="primary"
                onClick={runCheck}
                disabled={loading || !dealId || geography.trim() === ""}
              >
                {loading ? "Checking…" : "Check rent"}
              </button>
            </div>
          </div>

          {error && (
            <div className="status-banner error" role="alert">
              {error}
            </div>
          )}

          {result && (
            <div className={`rent-result status-${result.status}`}>
              <div className="rent-status">{STATUS_LABELS[result.status]}</div>
              <p>{result.note}</p>
              {result.market_rent !== null && result.deal_rent !== null && (
                <dl className="sens-readout">
                  <div>
                    <dt>Deal rent / unit</dt>
                    <dd>{formatMoney(result.deal_rent)}</dd>
                  </div>
                  <div>
                    <dt>
                      Market median
                      {result.source ? ` (${SOURCE_LABELS[result.source] ?? result.source})` : ""}
                    </dt>
                    <dd>{formatMoney(result.market_rent)}</dd>
                  </div>
                  <div>
                    <dt>Variance</dt>
                    <dd>
                      {result.variance !== null
                        ? `${result.variance >= 0 ? "+" : ""}${formatPercent(result.variance, 1)}`
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Underwritten rent growth</dt>
                    <dd>{formatPercent(result.deal_rent_growth)}</dd>
                  </div>
                  <div>
                    <dt>Market rent growth, trailing 12 mo</dt>
                    <dd>{formatPercent(result.market_yoy_growth, 1)}</dd>
                  </div>
                </dl>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
