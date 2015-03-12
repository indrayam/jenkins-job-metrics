import hudson.model.*
import hudson.triggers.*

listAllJobsWithTimerSpec(Hudson.instance.items)

def listAllJobsWithTimerSpec(items) {
    for(item in items) {
        if (item.class.canonicalName != 'com.cloudbees.hudson.plugins.folder.Folder') {
            if (item.class.canonicalName) {
                for(trigger in item.triggers.values()) {
                    if(trigger instanceof TimerTrigger) {
                        println("--- Timer trigger for " + item.name + " ---")
                        println(trigger.spec + '\n')
                    }
                }
            }
        } else {
        //print('[' + item.class.canonicalName + ']: ')
        //println(item.name)
        listAllJobsWithTimerSpec(((com.cloudbees.hudson.plugins.folder.Folder) item).getItems())
        }
    }
}