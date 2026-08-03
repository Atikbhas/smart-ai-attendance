-- Database schema for AI Attendance Management System
-- Generated from project SQLAlchemy models

CREATE DATABASE IF NOT EXISTS `ai_attendance` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `ai_attendance`;

CREATE TABLE `roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(50) NOT NULL UNIQUE,
  `description` VARCHAR(255),
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `first_name` VARCHAR(100) NOT NULL,
  `last_name` VARCHAR(100) NOT NULL,
  `role_id` INT NOT NULL,
  `last_login_at` DATETIME,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  INDEX `idx_users_email` (`email`),
  CONSTRAINT `fk_users_role_id` FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `departments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(150) NOT NULL,
  `code` VARCHAR(20) NOT NULL UNIQUE,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `courses` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(150) NOT NULL,
  `code` VARCHAR(20) NOT NULL UNIQUE,
  `department_id` INT NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_courses_department_id` FOREIGN KEY (`department_id`) REFERENCES `departments`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `subjects` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(150) NOT NULL,
  `code` VARCHAR(20) NOT NULL UNIQUE,
  `course_id` INT NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_subjects_course_id` FOREIGN KEY (`course_id`) REFERENCES `courses`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `professors` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `employee_code` VARCHAR(50) NOT NULL UNIQUE,
  `user_id` INT NOT NULL UNIQUE,
  `department_id` INT,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_professors_user_id` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_professors_department_id` FOREIGN KEY (`department_id`) REFERENCES `departments`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `students` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `roll_number` VARCHAR(50) NOT NULL UNIQUE,
  `gender` VARCHAR(30),
  `user_id` INT NOT NULL UNIQUE,
  `course_id` INT,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_students_user_id` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_students_course_id` FOREIGN KEY (`course_id`) REFERENCES `courses`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `classes` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL,
  `course_id` INT NOT NULL,
  `semester` INT NOT NULL,
  `section` VARCHAR(20),
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_classes_course_id` FOREIGN KEY (`course_id`) REFERENCES `courses`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `attendance_sessions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `method` VARCHAR(30) NOT NULL,
  `starts_at` DATETIME NOT NULL,
  `ends_at` DATETIME,
  `subject_id` INT NOT NULL,
  `professor_id` INT NOT NULL,
  `class_id` INT NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_attendance_sessions_subject_id` FOREIGN KEY (`subject_id`) REFERENCES `subjects`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_attendance_sessions_professor_id` FOREIGN KEY (`professor_id`) REFERENCES `professors`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_attendance_sessions_class_id` FOREIGN KEY (`class_id`) REFERENCES `classes`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `attendance` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `student_id` INT NOT NULL,
  `session_id` INT NOT NULL,
  `marked_at` DATETIME NOT NULL,
  `attendance_status` VARCHAR(30) NOT NULL,
  `confidence_score` FLOAT,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `uq_student_session` UNIQUE (`student_id`, `session_id`),
  CONSTRAINT `fk_attendance_student_id` FOREIGN KEY (`student_id`) REFERENCES `students`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_attendance_session_id` FOREIGN KEY (`session_id`) REFERENCES `attendance_sessions`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `face_encodings` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `student_id` INT NOT NULL,
  `encoding_path` VARCHAR(500) NOT NULL,
  `image_path` VARCHAR(500),
  `confidence_threshold` FLOAT NOT NULL DEFAULT 0.6,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_face_encodings_student_id` FOREIGN KEY (`student_id`) REFERENCES `students`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `qr_codes` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `student_id` INT NOT NULL,
  `token_hash` VARCHAR(255) NOT NULL,
  `expires_at` DATETIME,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_qr_codes_student_id` FOREIGN KEY (`student_id`) REFERENCES `students`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `leave_requests` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `student_id` INT NOT NULL,
  `reason` TEXT NOT NULL,
  `starts_on` DATE NOT NULL,
  `ends_on` DATE NOT NULL,
  `decision` VARCHAR(30) NOT NULL DEFAULT 'pending',
  `document_path` VARCHAR(500),
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_leave_requests_student_id` FOREIGN KEY (`student_id`) REFERENCES `students`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `notifications` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `title` VARCHAR(150) NOT NULL,
  `body` TEXT NOT NULL,
  `read_at` DATETIME,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_notifications_user_id` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `reports` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `generated_by_id` INT NOT NULL,
  `report_type` VARCHAR(80) NOT NULL,
  `file_path` VARCHAR(500) NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_reports_generated_by_id` FOREIGN KEY (`generated_by_id`) REFERENCES `users`(`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `activity_logs` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT,
  `action` VARCHAR(150) NOT NULL,
  `details` TEXT,
  `ip_address` VARCHAR(80),
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active',
  CONSTRAINT `fk_activity_logs_user_id` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `key` VARCHAR(120) NOT NULL UNIQUE,
  `value` TEXT,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `status` ENUM('active','inactive','archived') NOT NULL DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
