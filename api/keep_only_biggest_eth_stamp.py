import csv


def process_csv(input_file, output_file):
    with open(input_file, mode="r") as infile, open(
        output_file, mode="w", newline=""
    ) as outfile:
        print("Processing", input_file, "to", output_file)
        print("Did you remember to sort the input file?")
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        current_address = None
        max_stamp_value = 0
        max_stamp_name = ""
        latest_updated_at = ""

        for row in reader:
            address, stamp_name, updated_at, stamp_value = row
            stamp_value = int(stamp_value)  # Convert string to float

            # Check if we are still on the same address
            if address == current_address:
                # Update the max stamp value if the current one is greater
                if stamp_value > max_stamp_value:
                    max_stamp_value = stamp_value
                    max_stamp_name = stamp_name
                if updated_at > latest_updated_at:
                    latest_updated_at = updated_at
            else:
                # Write the previous address's max value if it exists
                if current_address is not None:
                    writer.writerow(
                        [
                            current_address,
                            max_stamp_name,
                            latest_updated_at,
                            max_stamp_value,
                        ]
                    )

                # Update the current address and its stamp value
                current_address = address
                max_stamp_value = stamp_value
                max_stamp_name = stamp_name
                latest_updated_at = updated_at

        # Don't forget to write the last address's data
        if current_address is not None:
            writer.writerow(
                [current_address, max_stamp_name, latest_updated_at, max_stamp_value]
            )

    print("Done!")


process_csv("eth_stamps.csv", "best_eth_stamps.csv")
