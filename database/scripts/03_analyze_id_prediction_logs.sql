CREATE TABLE IF NOT EXISTS analyze_id_prediction_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    logged_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    query_movie_id BIGINT NOT NULL,
    top_k INT NOT NULL,
    user_history_count INT NOT NULL DEFAULT 0,
    movie JSON NOT NULL,
    recommendations JSON NOT NULL,
    INDEX idx_analyze_id_prediction_logs_logged_at (logged_at DESC),
    INDEX idx_analyze_id_prediction_logs_query_movie_id (query_movie_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
