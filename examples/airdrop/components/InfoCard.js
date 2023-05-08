import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import styles from "@/styles/InfoCard.module.css";

export default function InfoCard({ title, icon, value }) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        <div className={styles.iconContainer}>
          <FontAwesomeIcon color="rgb(108, 122, 137)" icon={icon} />
        </div>
      </div>
      <p className={styles.value}>{value}</p>
    </div>
  );
}
