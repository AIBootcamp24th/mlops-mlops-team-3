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
