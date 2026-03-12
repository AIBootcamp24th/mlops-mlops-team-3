CREATE TABLE IF NOT EXISTS movies_raw (
    tmdb_id INT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    original_title VARCHAR(255),
    overview TEXT,
    release_date DATE,
    budget BIGINT DEFAULT 0,
    runtime INT DEFAULT 0,
    vote_average FLOAT,
    vote_count INT,
    popularity FLOAT,
    original_language VARCHAR(10),
    poster_path VARCHAR(255),
    genres JSON,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_language (original_language),
    INDEX idx_release_date (release_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS prediction_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tmdb_id INT,
    predicted_rating FLOAT NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tmdb_id) REFERENCES movies_raw(tmdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- tmdb/{champion}/*.csv 메타데이터 레지스트리 (Airflow 실행 이력 연계)
CREATE TABLE IF NOT EXISTS tmdb_dataset_registry (
    id INT AUTO_INCREMENT PRIMARY KEY,
    approved_run_id VARCHAR(64) NOT NULL,
    csv_type ENUM('train', 'infer', 'predictions') NOT NULL,
    s3_key VARCHAR(512) NOT NULL,
    row_count INT DEFAULT NULL,
    dag_id VARCHAR(256) DEFAULT NULL,
    dag_run_id VARCHAR(256) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_s3_key (s3_key),
    INDEX idx_approved_run (approved_run_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
