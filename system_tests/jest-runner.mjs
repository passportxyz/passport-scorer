import jest from "jest";

async function main() {
  try {
    await jest.run(["--runInBand"]);
  } catch (error) {
    console.error("Error running Jest:", error);
    process.exit(1);
  }
  console.log(JSON.stringify({ success: true }));
  process.exit(0);
}

main();
