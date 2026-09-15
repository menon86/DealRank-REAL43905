import { formatMoney } from "../lib/format";
import { SUB_ASSET_CLASS_LABELS } from "../lib/types";
import type { DealOut } from "../lib/types";

const MAX_SELECTION = 5;

interface DealListProps {
  deals: DealOut[];
  selectedIds: string[];
  onToggleSelected: (id: string) => void;
  onEdit: (deal: DealOut) => void;
  onDelete: (id: string) => void;
  onAddNew: () => void;
}

export function DealList({
  deals,
  selectedIds,
  onToggleSelected,
  onEdit,
  onDelete,
  onAddNew,
}: DealListProps) {
  return (
    <div className="card">
      <h2>Deals</h2>
      <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: -8 }}>
        Select 3–5 deals to compare and rank. {selectedIds.length} selected.
      </p>

      {deals.length === 0 ? (
        <div className="empty-state">No deals yet. Add your first one below.</div>
      ) : (
        <div>
          {deals.map((deal) => {
            const checked = selectedIds.includes(deal.id);
            const disableCheck = !checked && selectedIds.length >= MAX_SELECTION;
            return (
              <div className="deal-list-row" key={deal.id}>
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disableCheck}
                  onChange={() => onToggleSelected(deal.id)}
                  aria-label={`Select ${deal.name} for comparison`}
                />
                <span className="name">{deal.name}</span>
                <span className="sub-class">{SUB_ASSET_CLASS_LABELS[deal.sub_asset_class]}</span>
                <span style={{ width: 130, textAlign: "right", fontSize: 13 }}>
                  {formatMoney(deal.purchase_price)}
                </span>
                <button type="button" className="link" onClick={() => onEdit(deal)}>
                  Edit
                </button>
                <button type="button" className="link danger" onClick={() => onDelete(deal.id)}>
                  Delete
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="form-actions">
        <button type="button" className="primary" onClick={onAddNew}>
          Add deal
        </button>
      </div>
    </div>
  );
}
