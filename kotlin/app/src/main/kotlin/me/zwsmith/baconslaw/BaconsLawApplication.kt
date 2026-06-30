package me.zwsmith.baconslaw

import android.app.Application
import me.zwsmith.baconslaw.data.GameSessionRepository
import timber.log.Timber
import timber.log.Timber.Forest.plant


class BaconsLawApplication : Application() {

  val gameSessionRepository: GameSessionRepository = GameSessionRepository()

  override fun onCreate() {
    super.onCreate()

    if (BuildConfig.DEBUG) {
      plant(Timber.DebugTree())
    }
  }
}
