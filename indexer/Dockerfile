FROM rust:1.84.0

COPY ./ ./

RUN cargo build --release

CMD ["./target/release/indexer"]
