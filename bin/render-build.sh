#!/usr/bin/env bash
# exit on error
set -o errexit

bundle install

bundle exec rails assets:precompile
bundle exec rails assets:clean

# Run any pending migrations on every deploy.
bundle exec rails db:migrate

# Seed the database only the very first time (cheap check: no categories yet).
bundle exec rails runner "
  if Category.count.zero?
    Rails.logger.info('Seeding initial Growkit data...')
    load Rails.root.join('db', 'seeds.rb')
  end
"
