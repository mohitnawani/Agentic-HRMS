import { useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  searchableText?: (row: T) => string;
  searchPlaceholder?: string;
  initialPageSize?: number;
}

const PAGE_SIZES = [10, 25, 50];

export default function DataTable<T>({
  columns,
  data,
  emptyTitle = "No records found",
  rowKey,
  searchableText,
  searchPlaceholder = "Search records...",
  initialPageSize = 10,
}: DataTableProps<T>) {
  const [query, setQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);

  if (data.length === 0) {
    return <EmptyState title={emptyTitle} />;
  }

  const normalizedQuery = query.trim().toLowerCase();
  const filteredData = searchableText && normalizedQuery
    ? data.filter((row) => searchableText(row).toLowerCase().includes(normalizedQuery))
    : data;
  const totalPages = Math.max(1, Math.ceil(filteredData.length / pageSize));
  const page = Math.min(currentPage, totalPages);
  const startIndex = (page - 1) * pageSize;
  const pageRows = filteredData.slice(startIndex, startIndex + pageSize);
  const endIndex = Math.min(startIndex + pageSize, filteredData.length);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {searchableText && (
        <div className="border-b border-border bg-muted/30 p-3 sm:p-4">
          <div className="relative max-w-md">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setCurrentPage(1);
              }}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              className="bg-background pl-9"
            />
          </div>
        </div>
      )}

      {filteredData.length === 0 ? (
        <div className="p-4">
          <EmptyState
            title="No matching records"
            description="Try a different search term."
          />
        </div>
      ) : (
        <>
          <div className="max-h-[600px] overflow-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="sticky top-0 z-10 bg-muted text-primary shadow-[0_1px_0_var(--color-border)]">
                <tr>
                  {columns.map((col) => (
                    <th key={col.header} className="whitespace-nowrap px-4 py-3 text-left font-semibold">
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row, index) => (
                  <tr
                    key={rowKey(row, startIndex + index)}
                    className="border-t border-border transition-colors hover:bg-muted/40"
                  >
                    {columns.map((col) => (
                      <td key={col.header} className="px-4 py-3 align-middle">
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-col gap-3 border-t border-border bg-muted/20 px-3 py-3 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-4">
            <p className="text-muted-foreground" aria-live="polite">
              Showing {startIndex + 1}–{endIndex} of {filteredData.length}
              {normalizedQuery && filteredData.length !== data.length ? ` matching ${data.length} total` : ""}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-muted-foreground">Rows</span>
              <Select
                value={String(pageSize)}
                onValueChange={(value) => {
                  setPageSize(Number(value));
                  setCurrentPage(1);
                }}
              >
                <SelectTrigger className="h-9 w-[72px]" aria-label="Rows per page">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZES.map((size) => (
                    <SelectItem key={size} value={String(size)}>{size}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="min-w-20 text-center text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                type="button"
                size="icon"
                variant="outline"
                aria-label="Previous page"
                disabled={page === 1}
                onClick={() => setCurrentPage(page - 1)}
              >
                <ChevronLeft className="size-4" aria-hidden="true" />
              </Button>
              <Button
                type="button"
                size="icon"
                variant="outline"
                aria-label="Next page"
                disabled={page === totalPages}
                onClick={() => setCurrentPage(page + 1)}
              >
                <ChevronRight className="size-4" aria-hidden="true" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
