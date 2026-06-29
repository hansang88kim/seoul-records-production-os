import * as React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => React.ReactNode;
}

/** A compact, responsive data table driven by a column spec. */
export function CompactDataTable<T>({
  columns,
  rows,
  empty = "데이터가 없습니다.",
}: {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
}) {
  if (!rows.length) {
    return <p className="py-6 text-center text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((c) => (
            <TableHead key={c.key} className={c.align === "right" ? "text-right" : ""}>
              {c.header}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, i) => (
          <TableRow key={i}>
            {columns.map((c) => (
              <TableCell key={c.key} className={c.align === "right" ? "text-right" : ""}>
                {c.render(row)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
