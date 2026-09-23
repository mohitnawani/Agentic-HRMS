import type { ReactNode } from "react";
import EmptyState from "./EmptyState";

interface Column<T> {
  header: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  emptyTitle?: string;
  rowKey: (row: T, index: number) => string;
}

export default function DataTable<T>({ columns, data, emptyTitle = "No records found", rowKey }: DataTableProps<T>) {
  if (data.length === 0) {
    return <EmptyState title={emptyTitle} />;
  }
  return (
    <div className="max-h-[600px] overflow-auto rounded-xl border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-muted text-primary">
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th key={col.header} className="text-left font-medium px-4 py-2.5">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={rowKey(row, i)} className="border-t border-border hover:bg-muted/30">
              {columns.map((col) => (
                <td key={col.header} className="px-4 py-2.5">
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
