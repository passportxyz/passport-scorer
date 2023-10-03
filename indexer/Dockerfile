FROM rust:1.72.1

COPY ./ ./

RUN cargo build --release

CMD ["./target/release/indexer"]
