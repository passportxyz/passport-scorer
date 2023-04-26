import { useTable, usePagination } from "react-table";

export default function Table({ columns, data, removeFromAirdrop }) {
  const tableInstance = useTable(
    { columns, data, initialState: { pageIndex: 0 } },
    usePagination
  );

  const {
    getTableProps,
    getTableBodyProps,
    headerGroups,
    prepareRow,
    page,
    canPreviousPage,
    canNextPage,
    pageOptions,
    pageCount,
    gotoPage,
    nextPage,
    previousPage,
    setPageSize,
    state: { pageIndex, pageSize },
  } = tableInstance;

  return (
    // apply the table props
    <>
      <table
        style={{
          marginTop: "20px",
          borderCollapse: "collapse",
          width: "100%",
          borderLeft: "1px solid rgba(239,239,240,1)",
          borderRight: "1px solid rgba(239,239,240,1)",
          fontFamily: "sans-serif",
        }}
        {...getTableProps()}
      >
        <thead>
          {
            // Loop over the header rows
            headerGroups.map((headerGroup) => (
              // Apply the header row props
              <tr {...headerGroup.getHeaderGroupProps()}>
                {
                  // Loop over the headers in each row
                  headerGroup.headers.map((column) => {
                    // Apply the header cell props
                    if (column.Header === "Actions") {
                      return (
                        <th
                          {...column.getHeaderProps()}
                          style={{
                            background: "rgba(239,239,240,0.6)",
                            color: "rgba(149,165,166)",
                            padding: "15px",
                            textAlign: "center",
                          }}
                        >
                          {
                            // Render the header
                            column.render("Header")
                          }
                        </th>
                      );
                    } else {
                      return (
                        <th
                          {...column.getHeaderProps()}
                          style={{
                            background: "rgba(239,239,240,0.6)",
                            color: "rgba(149,165,166)",
                            padding: "15px",
                            textAlign: "left",
                          }}
                        >
                          {
                            // Render the header
                            column.render("Header")
                          }
                        </th>
                      );
                    }
                  })
                }
              </tr>
            ))
          }
        </thead>
        {/* Apply the table body props */}
        <tbody {...getTableBodyProps()}>
          {
            // Loop over the table rows
            page.map((row) => {
              // Prepare the row for display
              prepareRow(row);
              return (
                // Apply the row props
                <tr {...row.getRowProps()}>
                  {
                    // Loop over the rows cells
                    row.cells.map((cell) => {
                      if (cell.column.Header === "Actions") {
                        return (
                          <td
                            {...cell.getCellProps()}
                            style={{
                              padding: "15px",
                              borderBottom: "solid 1px rgba(239,239,240,1)",
                              display: "flex",
                              justifyContent: "center",
                            }}
                          >
                            <button
                              onClick={() => {
                                removeFromAirdrop(cell.row.original.address);
                              }}
                              type="button"
                              style={{
                                border: "none",
                                background: "none",
                                cursor: "pointer",
                              }}
                            >
                              🗑️
                            </button>
                          </td>
                        );
                      }
                      // Apply the cell props
                      return (
                        <td
                          {...cell.getCellProps()}
                          style={{
                            padding: "15px",
                            borderBottom: "solid 1px rgba(239,239,240,1)",
                            background: "",
                          }}
                        >
                          {
                            // Render the cell contents
                            cell.render("Cell")
                          }
                        </td>
                      );
                    })
                  }
                </tr>
              );
            })
          }
        </tbody>
      </table>
      <div
        style={{
          marginTop: "15px",
          display: "flex",
          justifyContent: "flex-end",
        }}
      >
        <button
          style={{ marginRight: "5px" }}
          onClick={() => gotoPage(0)}
          disabled={!canPreviousPage}
        >
          {"<<"}
        </button>{" "}
        <button
          style={{ marginRight: "5px" }}
          onClick={() => previousPage()}
          disabled={!canPreviousPage}
        >
          {"<"}
        </button>{" "}
        <button
          style={{ marginRight: "5px" }}
          onClick={() => nextPage()}
          disabled={!canNextPage}
        >
          {">"}
        </button>{" "}
        <button onClick={() => gotoPage(pageCount - 1)} disabled={!canNextPage}>
          {">>"}
        </button>{" "}
        <div
          style={{
            marginLeft: "10px",
            marginRight: "10px",
            fontFamily: "sans-serif",
          }}
        >
          <span>
            Page{" "}
            <strong>
              {pageIndex + 1} of {pageOptions.length}
            </strong>{" "}
          </span>
        </div>
      </div>
    </>
  );
}
