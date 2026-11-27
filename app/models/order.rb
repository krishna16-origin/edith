class Order < ApplicationRecord
  belongs_to :user
  has_many :order_items, dependent: :destroy
  has_many :products, through: :order_items

  validates :total_amount, presence: true

  enum status: { placed: 0, shipped: 1, delivered: 2, cancelled: 3 }
end
