class SessionsController < ApplicationController
  def new
    redirect_to root_path if logged_in?
  end

  def create
    phone_number = params[:phone_number].to_s.strip
    name = params[:name].to_s.strip

    if name.blank? || phone_number.blank?
      flash.now[:alert] = "Please enter both your name and mobile number."
      return render :new, status: :unprocessable_entity
    end

    unless phone_number.match?(/\A\d{10}\z/)
      flash.now[:alert] = "Please enter a valid 10-digit mobile number."
      return render :new, status: :unprocessable_entity
    end

    user = User.find_or_initialize_by(phone_number: phone_number)
    user.name = name

    if user.save
      session[:user_id] = user.id
      redirect_to root_path, notice: "Welcome, #{user.name}!"
    else
      flash.now[:alert] = user.errors.full_messages.to_sentence
      render :new, status: :unprocessable_entity
    end
  end

  def destroy
    reset_session
    redirect_to root_path, notice: "You have been logged out."
  end
end
