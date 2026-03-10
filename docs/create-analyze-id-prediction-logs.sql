-- /analyze/id 전용 로깅 테이블 (MySQL 8.0+)
create table if not exists analyze_id_prediction_logs (
  id bigint auto_increment primary key,
  logged_at datetime(6) not null default current_timestamp(6),
  query_movie_id bigint not null,
  top_k int not null,
  user_history_count int not null default 0,
  movie json not null,
  recommendations json not null,
  index idx_analyze_id_prediction_logs_logged_at (logged_at desc),
  index idx_analyze_id_prediction_logs_query_movie_id (query_movie_id)
) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_unicode_ci;
