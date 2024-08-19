import pandas as pd

errors = pd.read_csv("neg_ones_addresses.csv")

# convert string list to list
errors["Model"] = errors["Model"].apply(eval)


error_types = set([item for sublist in errors["Model"] for item in sublist])
print(error_types, "error_types")


error_dfs = {
    error_type: pd.DataFrame(columns=["Address"]) for error_type in error_types
}


for index, row in errors.iterrows():
    address = row["Address"]
    models = row["Model"]
    for model in models:
        new_row = pd.DataFrame({"Address": [address]})
        error_dfs[model] = pd.concat([error_dfs[model], new_row], ignore_index=True)


for error_type, df in error_dfs.items():
    output_filename = f"{error_type}_errors.csv"
    df.to_csv(output_filename, index=False)
    print(f"Created {output_filename} with {len(df)} addresses")

print("Processing complete.")
