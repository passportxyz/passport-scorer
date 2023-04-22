import { useTable, usePagination } from "react-table";

export default function Table({ columns, data, removeFromAirdrop }) {
  const tableInstance = useTable({ columns, data });

  const { getTableProps, getTableBodyProps, headerGroups, rows, prepareRow } =
    tableInstance;

  return (
    // apply the table props
    <table
      style={{ marginTop: "20px", borderCollapse: "collapse" }}
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
                headerGroup.headers.map((column) => (
                  // Apply the header cell props
                  <th
                    {...column.getHeaderProps()}
                    style={{
                      borderBottom: "solid 1px #D3D3D3",
                      background: "#D3D3D3",
                      color: "black",
                      fontWeight: "bold",
                      padding: "5px",
                    }}
                  >
                    {
                      // Render the header
                      column.render("Header")
                    }
                  </th>
                ))
              }
            </tr>
          ))
        }
      </thead>
      {/* Apply the table body props */}
      <tbody {...getTableBodyProps()}>
        {
          // Loop over the table rows
          rows.map((row) => {
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
                            padding: "10px",
                            border: "solid 1px #D3D3D3",
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
                          padding: "10px",
                          border: "solid 1px #D3D3D3",
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
  );
}
