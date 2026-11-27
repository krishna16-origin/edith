class User < ApplicationRecord
  has_one :cart, dependent: :destroy
  has_many :orders, dependent: :destroy

  validates :name, presence: true
  validates :phone_number, presence: true, uniqueness: true,
            format: { with: /\A\d{10}\z/, message: "must be a valid 10-digit mobile number" }

  after_create :assign_cart

  private

  def assign_cart
    create_cart! unless cart
  end
end
