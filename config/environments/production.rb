Rails.application.configure do
  config.enable_reloading = false
  config.eager_load = true
  config.consider_all_requests_local = false

  config.action_controller.perform_caching = true
  config.public_file_server.enabled = ActiveModel::Type::Boolean.new.cast(ENV["RAILS_SERVE_STATIC_FILES"])

  config.assets.compile = false

  config.log_level = :info
  config.log_tags = [:request_id]

  if ENV["RAILS_LOG_TO_STDOUT"].present?
    logger           = ActiveSupport::Logger.new($stdout)
    logger.formatter = config.log_formatter
    config.logger    = ActiveSupport::TaggedLogging.new(logger)
  end

  config.active_support.report_deprecations = false

  config.i18n.fallbacks = true

  config.active_record.dump_schema_after_migration = false

  config.hosts << ENV["APP_HOST"] if ENV["APP_HOST"]
end
