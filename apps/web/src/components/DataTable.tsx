import type { HTMLAttributes, ReactNode } from "react";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  render(row: T): ReactNode;
  align?: "left" | "right";
};

type DataTableProps<T> = {
  caption: string;
  columns: ReadonlyArray<DataTableColumn<T>>;
  rows: ReadonlyArray<T>;
  rowKey(row: T): string;
  emptyMessage?: string;
  rowProps?(row: T): HTMLAttributes<HTMLTableRowElement>;
};

/**
 * Accessible table used both as the chart alternative and as the non-map view
 * of the municipal layer. Captions, column scopes and an empty row are always
 * rendered so assistive technology never encounters an unlabelled table.
 */
export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  emptyMessage = "No hay datos para los filtros seleccionados.",
  rowProps,
}: DataTableProps<T>) {
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      role="region"
      aria-label={`${caption} (tabla desplazable)`}
    >
      <table className="data-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={column.align === "right" ? "is-numeric" : undefined}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="data-table__empty" colSpan={columns.length}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={rowKey(row)} {...rowProps?.(row)}>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={column.align === "right" ? "is-numeric" : undefined}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
