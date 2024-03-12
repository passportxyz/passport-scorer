FROM rust:1.76.0

COPY ./ ./

RUN cargo build --release

CMD ["./target/release/indexer"]
