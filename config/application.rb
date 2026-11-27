require_relative "boot"

require "rails/all"

Bundler.require(*Rails.groups)

module Growkit
  class Application < Rails::Application
    config.load_defaults 7.1
    config.autoload_lib(ignore: %w[assets tasks])
    config.time_zone = "Asia/Kolkata"
    config.active_record.default_timezone = :local
    config.generators { |g| g.test_framework false }
  end
end
