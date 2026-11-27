class CreateUsers < ActiveRecord::Migration[7.1]
  def change
    create_table :users do |t|
      t.string :phone_number, null: false
      t.string :name, null: false
      t.timestamps
    end
    add_index :users, :phone_number, unique: true
  end
end
